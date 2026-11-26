"""Thin views: read from the ReportProvider and render. No business logic here."""

import hashlib
import json
import secrets
import uuid
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import models, transaction
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.astrology.domain.chart import BirthData
from apps.astrology.domain.weather import weather as sky_weather
from apps.astrology.infrastructure.ephemeris import SkyfieldEphemeris
from apps.compatibility import date_ideas, places, story
from apps.compatibility import dates as pair_dates
from apps.compatibility import intimacy as intimacy_wishes
from apps.compatibility import plan as habit_plan
from apps.compatibility import tree as pair_tree
from apps.compatibility import week as pair_week
from apps.compatibility import wishes as pair_wishes
from apps.compatibility.access import grant_trial, mark_paid, open_gift, plus_for_pair, plus_until, redeem_gift, unlocked
from apps.compatibility.domain.archetypes import DYNAMICS, ELEMENTS, MODES, ROLES, dynamic_for, pair_name
from apps.compatibility.domain.report import Report, ReportUnavailable
from apps.compatibility.infrastructure import oauth, yookassa
from apps.compatibility.infrastructure.telegram import send_message
from apps.compatibility.models import DailyAnswer, Device, IntimacyAnswer, Owner, Pair, Person, Purchase, QuizAnswer, StoredReport
from apps.compatibility.notify import notify_partner
from apps.compatibility.services import (
    birth_payload,
    check_login_code,
    create_pair,
    daily_state,
    email_hash,
    forget_device,
    from_login_link,
    from_share_token,
    get_device,
    get_owner,
    invite_code,
    issue_login_code,
    latest_ready,
    login_link_token,
    pair_by_code,
    pairs_of,
    person_input,
    remember_owner,
    report_of,
    request_report,
    share_token,
    side_of,
    sign_in,
    update_person,
)
from apps.compatibility.streak import pair_streak
from apps.core.domain.names import acc as gen_acc
from apps.core.domain.names import gen
from apps.psychology.domain import scoring as psy
from apps.psychology.domain.instruments import ITEMS, LIKERT, SECTIONS
from apps.web.avatars import AVATARS
from config.container import report_provider

# What an ordinary reader needs: the answer, the spheres, what to do. The layers live one level down.
REPORT_TABS = {  # title, icon, short title for the phone tab bar
    "razbor": ("Разбор", "book-open", "Разбор"),
    "habits": ("Вместе", "sprout", "Вместе"),
    "layers": ("Из чего сложилось", "blocks", "Слои"),
}
LAYER_TABS = {
    "astrology": ("Астрология", "orbit"),
    "psychology": ("Психология", "brain"),
    "numbers": ("Числа", "hash"),
    "tarot": ("Таро", "layers"),
}
UNIVERSE_TAB = {"astrology": "astrology", "psychology": "psychology", "numerology": "numbers", "tarot": "tarot"}

# Landing showcase: 6 of the 78 pair types, covering all four dynamics.
EXAMPLE_PAIRS = [
    ("sail", "compass"),
    ("fire", "fire"),
    ("spark", "harbor"),
    ("star", "wind"),
    ("garden", "lighthouse"),
    ("bridge", "river"),
]


def _example(a: str, b: str) -> dict:
    ra, rb = ROLES[a], ROLES[b]
    tagline = f"Оба {ra.verb}" if a == b else f"Один {ra.verb}, другой — {rb.verb}"
    return {"a": a, "b": b, "name": pair_name(ra, rb), "tagline": tagline, "dynamic": dynamic_for(ra, rb)}


WIZARD_MODES = [
    ("quick", "Быстрый", "≈ 30 секунд", "Только даты рождения", ["балл пары", "3 категории", "арканы"], "zap"),
    (
        "extended",
        "Расширенный",
        "≈ 2 минуты",
        "Даты, время и место рождения",
        ["полная синастрия", "дома и Асцендент", "числа и таро"],
        "orbit",
    ),
    ("deep", "Глубокий", "≈ 10 минут", "Всё выше + короткие анкеты", ["научный слой", "Готтман", "план привычек"], "brain"),
]
WIZARD_QUIZZES = [
    ("Большая пятёрка", "10 утверждений о характере", "user-round"),
    ("Привязанность", "6 вопросов о близости", "heart-handshake"),
    ("Конфликт и стресс", "4 ситуации из жизни пары", "messages-square"),
    ("MBTI", "опционально, не влияет на балл", "shapes"),
]
CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Самара",
    "Ростов-на-Дону",
    "Краснодар",
    "Владивосток",
    "Калининград",
    "Минск",
    "Алматы",
    "Тбилиси",
    "Ереван",
    "Берлин",
    "Лондон",
    "Нью-Йорк",
]

PLANS = [  # what is gated: access.plus_for_pair (quiz, diary, reservation, date plan), access.unlocked (deep or a paid year)
    {
        "kind": "free",
        "glyph": "sprout",
        "name": "Бесплатно",
        "note": "Всё, чтобы каждый день быть ближе",
        "price": "0 ₽",
        "per": "навсегда",
        "cta": "Начать",
        "small": "без карты · вход по почте за минуту",
        "features": [
            "Тип пары, балл и первая сфера",
            "Вопрос дня, серия и наше дерево",
            "Календарь и карта желаний",
            "«Думаю о тебе» и «Свидание недели»",
            "«Близость 18+» из ваших общих «да»",
        ],
    },
    {
        "kind": "deep",
        "glyph": "star",
        "name": "Глубокий разбор",
        "note": "Почему вы спорите об одном и том же — и что с этим делать",
        "price": f"{settings.PRICE_DEEP} ₽",
        "per": "разово, навсегда",
        "cta": "Выбрать разбор",
        "small": "за одну пару · открывается вам обоим · чек на почту",
        "features": [
            "Все 13 сфер: что работает и где зона внимания",
            "Сценарии в спорах и близости — с исследованиями",
            "«Неделя пары»: 7 шагов из разбора",
            "4 слоя с картами и графиками",
            "PDF, открыт вам обоим",
        ],
    },
    {
        "kind": "plus",
        "glyph": "heart",
        "name": "Пара+",
        "note": "Чтобы забота друг о друге стала привычкой",
        "price": f"{settings.PRICE_PLUS} ₽",
        "per": "в месяц",
        "cta": "Подключить",
        "small": "не продлевается сама · без карты на пробной неделе",
        "year_extra": "Полные разборы всех ваших пар",
        "features": [
            "Квиз недели: кто кого знает лучше",
            "Дневник пары: все ответы на вопросы дня",
            "Тихая бронь подарков",
            "Пошаговый план свидания",
        ],
    },
]
COMPARE = [
    ("Тип пары, балл и первая сфера", (True, True, True)),
    ("Вопрос дня, серия и наше дерево", (True, True, True)),
    ("Календарь пары и карта желаний", (True, True, True)),
    ("«Думаю о тебе» и «спасибо за…»", (True, True, True)),
    ("«Близость 18+» из общих «да»", (True, True, True)),
    ("Все 13 сфер, научный слой и сценарии", (False, True, "с годом")),
    ("Четыре вселенные", ("2 из 4", True, "с годом")),
    ("«Неделя пары»", ("1-й день", True, "с годом")),
    ("PDF", (False, True, "с годом")),
    ("Для всех ваших пар", (False, "одна пара", "с годом")),
    ("«Свидание недели»", ("идея", "идея", "идея и план")),
    ("Квиз недели", (False, False, True)),
    ("Дневник ответов", (False, False, True)),
    ("Тихая бронь подарков", (False, False, True)),
    ("Открывается партнёру", (True, True, True)),
]
FAQ_PRICING = [
    ("Платить нужно обоим?", "Нет. Разбор открывается вам обоим, а «Пара+» одного из вас работает для всей пары."),
    (
        "Что будет после пробной недели?",
        "Ничего не спишется: карту мы не просим. Закроются квиз, дневник ответов, тихая бронь и план свидания. "
        "Дерево, календарь, желания и вопрос дня останутся с вами.",
    ),
    (
        "Чем разбор отличается от «Пары+»?",
        "Разбор — разовая покупка: полный текст о вашей паре, навсегда и вам обоим. «Пара+» — то, что каждый день: квиз, "
        "дневник, тихая бронь и план свидания. Год «Пары+» вдобавок открывает все ваши разборы, пока действует.",
    ),
    ("Можно вернуть деньги?", "Да, в течение 14 дней, если разбор не открывали. «Пара+» не продлевается сама."),
]

MARQUEE = [
    [
        ("Венера △ Марс · орб 2.1°", "a"),
        ("Надёжная привязанность × 2", "sci"),
        ("Аркан пары · I Маг", "pair"),
        ("Число пути 6 + 7", "sym"),
        ("Индекс восстановления 78", "sci"),
        ("Луна ⚹ Луна · орб 3.4°", "b"),
        ("Тип пары · Компас и парус", "pair"),
        ("Открытость 78 / 71", "sci"),
    ],
    [
        ("Меркурий □ Меркурий · орб 1.8°", "b"),
        ("Критика: низкий уровень", "sci"),
        ("Матрица · «Отношения» 6 и 14", "sym"),
        ("Солнце ☍ Солнце", "a"),
        ("Справедливость × Повешенный", "pair"),
        ("Экстраверсия 70 / 38", "sci"),
        ("Число пары 4 · фундамент", "sym"),
        ("Юпитер △ Солнце · орб 2.7°", "a"),
    ],
]
STORY = [
    (
        "Считаем четыре вселенные",
        "Эфемериды, нумерология, арканы и психологические шкалы — каждая система даёт свой балл. Никакой магии: детерминированный код.",
        "calculator",
    ),
    (
        "Сверяем, где они сходятся",
        "Индекс согласия показывает, видят ли вселенные одно и то же. Расхождения не прячем — объясняем.",
        "scale",
    ),
    (
        "Объясняем каждый вывод",
        "Под любым утверждением — «Почему так»: конкретный аспект, число или шкала. ИИ лишь связывает проверенные факты.",
        "search-check",
    ),
    (
        "Собираем отчёт и план",
        "Тип пары, зоны синергии и трения, матрица рисков и маленькие привычки, которые реально помогают.",
        "sparkles",
    ),
]

FAQ = [
    (
        "Это предсказание?",
        "Нет. Мы не предсказываем события и не решаем за вас. Отчёт показывает сильные стороны пары и зоны, где понадобятся договорённости.",
    ),
    (
        "Что если я не знаю время рождения?",
        "Ничего страшного: мы посчитаем всё, что можно по дате, и честно покажем, что не учтено — например, дома и Асцендент.",
    ),
    (
        "Почему психология отдельно?",
        "Это единственный слой с научной базой. Мы показываем его рядом с символическими, но не смешиваем, чтобы он оставался читаемым.",
    ),
    (
        "Партнёру нужно регистрироваться?",
        "Нет. Вы отправляете ссылку, партнёр проходит свою часть — и вы видите общий разбор, когда ответили оба.",
    ),
    (
        "Нужно регистрироваться?",
        "Нет. Разборы хранятся на вашем устройстве. Если захотите открыть их на другом телефоне — пришлём ссылку на почту, без паролей.",
    ),
    (
        "Что с моими данными?",
        "Данные рождения и анкеты шифруются, используются только для отчёта и удаляются одной кнопкой. Соответствие 152-ФЗ и GDPR.",
    ),
    ("Сколько стоит?", "Быстрый отчёт бесплатный. Глубокий разбор, парный режим и PDF — по прозрачной цене, без автосписаний."),
]

SPHERE_TITLES = [
    ("attraction", "Притяжение"),
    ("sex", "Секс"),
    ("emotions", "Эмоции"),
    ("talk", "Общение"),
    ("conflicts", "Конфликты"),
    ("trust", "Доверие"),
    ("power", "Власть"),
    ("shadows", "Тени"),
    ("home", "Быт"),
    ("money", "Деньги"),
    ("plans", "Планы"),
    ("people", "Люди"),
    ("growth", "Рост"),
]
REPORT_CHAPTERS = [
    ("01", "type", "Тип пары"),
    ("02", "you", "Каждый из вас"),
    ("03", "spheres", "Сферы жизни"),
    ("04", "diverge", "Где вы расходитесь"),
    ("05", "plan", "План"),
    ("06", "questions", "Вопросы"),
]

PAGES = {
    # url name -> template; static screens that only need the base context
    "start": "pages/start.html",
    "account": "pages/account.html",
    "states": "pages/states.html",
    "disclaimer": "pages/disclaimer.html",
    "offline": "pages/offline.html",
    "pair_invite": "pages/pair_invite.html",
    "pair_waiting": "pages/pair_waiting.html",
}


def _scenario(request: HttpRequest) -> str:
    return request.session.get("scenario", "ideal")


DEV_ONLY = {"states"}  # prototype screens, not for users


def page(request: HttpRequest, name: str) -> HttpResponse:
    if name in DEV_ONLY and not settings.DEV_SCREENS:
        raise Http404
    return render(request, PAGES[name])


LEGAL = {"privacy": "privacy-policy.md", "consent": "consent.md", "terms": "offer.md"}
LEGAL_LINKS = {"(privacy-policy.md)": "(/privacy/)", "(consent.md)": "(/consent/)", "(offer.md)": "(/terms/)"}


def legal(request: HttpRequest, doc: str) -> HttpResponse:
    """The documents are kept as Markdown in docs/legal so a lawyer edits one file and the site follows."""
    import markdown

    text = (settings.BASE_DIR / "docs" / "legal" / LEGAL[doc]).read_text(encoding="utf-8")
    for md, url in LEGAL_LINKS.items():
        text = text.replace(md, url)
    title, _, body = text.partition("\n")
    return render(
        request, "pages/legal.html", {"title": title.lstrip("# "), "body": markdown.markdown(body, extensions=["tables"]), "doc": doc}
    )


def set_scenario(request: HttpRequest, key: str) -> HttpResponse:
    if not settings.DEV_SCREENS:
        raise Http404
    if key in {s.key for s in report_provider().scenarios()}:
        request.session["scenario"] = key
    back = request.GET.get("next", "/")
    return redirect(back if url_has_allowed_host_and_scheme(back, {request.get_host()}) else "/")


# ── report rendering (shared by the demo report and stored reports) ───────
def _render_report(request: HttpRequest, report: Report, template: str, rbase: str, extra: dict | None = None, **ctx) -> HttpResponse:
    a, b = report.partners
    if ctx.pop("deal", False) and report.tarot.available and report.tarot.a and report.tarot.b and report.tarot.pair:
        t = report.tarot  # left card flies in from the right of the deck, right card from the left
        ctx["deal_cards"] = [
            (t.a, "a", a.name, "w-[6.5rem] sm:w-40", "118%", "-14deg"),
            (t.pair, "pair", "Аркан пары", "w-32 sm:w-52", "0%", "4deg"),
            (t.b, "b", b.name, "w-[6.5rem] sm:w-40", "-118%", "12deg"),
        ]
    pt = report.pair_type
    roles = {"role_a": ROLES[pt.role_a], "role_b": ROLES[pt.role_b], "dynamic": DYNAMICS[pt.dynamic], "elements": ELEMENTS, "modes": MODES}
    links = {
        "chapters": REPORT_CHAPTERS,
        "rbase": rbase,
        "quiz_url": reverse("quiz"),
        "invite_url": reverse("pair_invite"),
        "share_url": request.build_absolute_uri(rbase + "share/"),
        # «add time and place» goes back to the wizard with this pair's data filled in (stored reports set it)
        "upgrade_url": (extra or {}).get("upgrade_url") or reverse("wizard") + "?mode=extended",
    }
    astro = report.astrology
    from apps.astrology.domain.chart import ELEMENT_RU, MODALITY_RU

    d = report.depth
    charts_extra = {
        "depth_items": [
            (d.get("dates", True), "Даты рождения", "планеты, числа, арканы", None),
            (
                d.get("time_place_a", False),
                f"Время и место · {a.name}",
                "дома, Асцендент, точная Луна",
                links["upgrade_url"],
            ),
            (d.get("time_place_b", False), f"Время и место · {b.name}", "наложения домов, композит", links["upgrade_url"]),
            (d.get("psych", False), "Анкеты обоих", "научный слой: привязанность, конфликт, тени", links["quiz_url"]),
        ]
    }
    charts = {
        **charts_extra,
        "planet_tables": [("a", astro.planets_a), ("b", astro.planets_b)],
        "overlay_sides": [("a", f"Планеты {gen(a.name)} в домах {gen(b.name)}"), ("b", f"Планеты {gen(b.name)} в домах {gen(a.name)}")],
        "sphere_titles": SPHERE_TITLES,
        "balance_rows": [
            ("Стихии", [(ELEMENT_RU[k].capitalize(), astro.balance_a.elements[k], astro.balance_b.elements[k]) for k in ELEMENT_RU]),
            ("Кресты", [(MODALITY_RU[k].capitalize(), astro.balance_a.modalities[k], astro.balance_b.modalities[k]) for k in MODALITY_RU]),
        ]
        if astro.balance_a and astro.balance_b
        else [],
    }
    return render(
        request,
        template,
        {
            "r": report,
            "a": a,
            "b": b,
            "tabs": REPORT_TABS,
            "layer_tabs": LAYER_TABS,
            "universe_tab": UNIVERSE_TAB,
            "plan": _plan_ctx(request, (extra or {}).get("stored")),
            **roles,
            **links,
            **charts,
            **(extra or {}),
            **ctx,
        },
    )


def _my_side(request: HttpRequest, pair: Pair | None) -> str:
    owner = get_owner(request)
    return side_of(owner, pair) if owner and pair else "a"


def _plan_ctx(request: HttpRequest, stored: StoredReport | None) -> dict:
    raw = stored.pair.plan if stored else request.session.get("plan", {})
    side = _my_side(request, stored.pair if stored else None)
    return {**habit_plan.state(raw, timezone.localdate(), side), "rid": str(stored.id) if stored else "", "max": habit_plan.MAX_PICK}


def _plan_target(request: HttpRequest) -> tuple[dict, list[str], Pair | None]:
    """The plan being edited: the owner's stored pair when `rid` is given, otherwise the demo plan in the session."""
    if rid := request.POST.get("rid"):
        stored = _owned_report(request, rid)
        return stored.pair.plan, [h.title for h in report_of(stored).habits], stored.pair
    report = report_provider().get_report(_scenario(request))
    return request.session.get("plan", {}), [h.title for h in report.habits], None


def _plan_save(request: HttpRequest, plan: dict, pair: Pair | None) -> JsonResponse:
    if pair:
        pair.plan = plan
        pair.save(update_fields=["plan"])
    else:
        request.session["plan"] = plan
    return JsonResponse(habit_plan.state(plan, timezone.localdate(), _my_side(request, pair)))


@require_POST
def plan_pick(request: HttpRequest) -> HttpResponse:
    plan, allowed, pair = _plan_target(request)
    return _plan_save(request, habit_plan.pick(plan, request.POST.getlist("habit"), allowed, timezone.localdate()), pair)


@require_POST
def plan_done(request: HttpRequest) -> HttpResponse:
    plan, _, pair = _plan_target(request)
    side = _my_side(request, pair)
    return _plan_save(request, habit_plan.toggle(plan, request.POST.get("habit", ""), timezone.localdate(), side), pair)


def _demo(request: HttpRequest, template: str, **ctx) -> HttpResponse:
    try:
        report = report_provider().get_report(_scenario(request))
    except ReportUnavailable:
        return render(request, "report/error.html", {"retry_url": reverse("generating")}, status=503)
    return _render_report(request, report, template, reverse("report"), **ctx)


def sign_compatibility(request: HttpRequest) -> HttpResponse:
    """Sun signs as a symbolic first look: kinds of connection with explanations, never a score or a «worst» sign."""
    from apps.astrology.domain.chart import ELEMENT_RU, SIGN_ELEMENT, SIGN_GLYPH, SIGNS
    from apps.astrology.domain.signs import groups
    from apps.knowledge.infrastructure.repository import KnowledgeRepository

    options = [{"idx": idx, "name": name, "glyph": SIGN_GLYPH[idx]} for idx, name in enumerate(SIGNS)]
    raw = request.GET.get("sign", "")
    selected = options[int(raw)] if raw.isdigit() and int(raw) < len(options) else None
    sections = []
    if selected:
        kb = KnowledgeRepository()
        me = int(raw)
        for g in groups(me):
            cards = []
            for m in g["signs"]:
                details = kb.data(m["knowledge_key"])
                pair = "+".join(sorted((SIGN_ELEMENT[me], SIGN_ELEMENT[m["idx"]])))
                cards.append(
                    {
                        **m,
                        "glyph": SIGN_GLYPH[m["idx"]],
                        "element_name": ELEMENT_RU[m["element"]].capitalize(),
                        "elements": kb.text(f"SUNELEM:{pair}"),
                        "plus": details.get("plus", ""),
                        "minus": details.get("minus", ""),
                        "advice": details.get("advice", ""),
                    }
                )
            sections.append({**g, "signs": cards})
    return render(request, "pages/sign_compatibility.html", {"sign_options": options, "selected_sign": selected, "sections": sections})


def _pair_path(owner: Owner, pair: Pair, together: int, stored: StoredReport | None) -> dict | None:
    """The couple's first steps as one card on «Вдвоём» until they're done — invite the partner, the questionnaires
    together, three days answering together — then, three months on, a fresh look. None when there is nothing to do."""
    side = side_of(owner, pair)
    me, partner = (pair.a, pair.b) if side == "a" else (pair.b, pair.a)
    invite = reverse("invite_new", args=[pair.id]) if pair.owner_id == owner.id else reverse("pair_invite")
    steps = [
        (bool(pair.partner_id), f"Позвать {gen_acc(partner.name)}", "Разбор станет общим, а вопрос дня — на двоих.", invite, "Пригласить"),
        (bool(me.answers and partner.answers), "Анкеты вдвоём", "Психология двоих делает разбор точным: где вы совпадаете и где спорите.",
         "" if me.answers else reverse("person_quiz", args=[me.id]), f"Ждём {gen_acc(partner.name)}" if me.answers else "Пройти анкету"),
        (together >= 3, "Три дня вместе", "Ответьте оба на вопрос дня три дня подряд — и вы в ритме, а дерево растёт.",
         reverse("daily"), f"Вопрос дня · {together} из 3"),
    ]  # fmt: skip
    for n, (done, title, text, url, cta) in enumerate(steps, 1):
        if not done:
            return {"n": n, "of": len(steps), "title": title, "text": text, "url": url, "cta": cta}
    if stored and (timezone.now() - stored.created_at).days >= 90:
        return {"n": 0, "title": "Пора взглянуть заново", "text": "Прошло три месяца: пройдите анкеты ещё раз и посмотрите, как вы изменились.",
                "url": reverse("pair_story", args=[pair.id]), "cta": "Пересчитать"}  # fmt: skip
    return None


def landing(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    pair = pairs_of(owner).order_by("-created_at").first() if owner and owner.is_account else None
    if pair and "about" not in request.GET:  # a couple opens on «Вдвоём»; ?about still shows the page about Duoverse
        return redirect("pair_invite")
    r = report_provider().get_report("ideal")
    return render(
        request,
        "pages/landing.html",
        {
            "r": r,
            "a": r.partners[0],
            "b": r.partners[1],
            "pair_types": [_example(a, b) for a, b in EXAMPLE_PAIRS],
            "faq": FAQ,
            "marquee": MARQUEE,
            "story": STORY,
        },
    )


def pricing(request: HttpRequest) -> HttpResponse:
    ctx = {
        "plans": PLANS,
        "compare": COMPARE,
        "faq": FAQ_PRICING,
        "price_plus_year": settings.PRICE_PLUS_YEAR,
        "price_deep": settings.PRICE_DEEP,
    }
    return render(request, "pages/pricing.html", ctx)


def report(request: HttpRequest) -> HttpResponse:
    return _demo(request, "report/dashboard.html", tab="overview", reveal=request.GET.get("reveal") == "1")


def report_tab(request: HttpRequest, tab: str) -> HttpResponse:
    if tab == "weights":
        return _demo(request, "pages/weights.html")
    if tab not in REPORT_TABS and tab not in LAYER_TABS:
        raise Http404
    return _demo(request, f"report/{tab}.html", tab=tab, deal=tab == "tarot")


def share(request: HttpRequest) -> HttpResponse:
    return _demo(request, "report/share.html", tab="share")


def _card_svg(request: HttpRequest, r: Report) -> HttpResponse:
    from apps.web.templatetags.art import pair_poster_svg

    top = sorted(r.categories, key=lambda c: c.score, reverse=True)[:3]
    ctx = {
        "r": r,
        "a": r.partners[0],
        "b": r.partners[1],
        "top": top,
        "poster_svg": pair_poster_svg(r.pair_type.role_a, r.pair_type.role_b),
    }
    resp = render(request, "report/share_card.svg", ctx, content_type="image/svg+xml; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="duoverse-pair.svg"'
    return resp


def share_card(request: HttpRequest) -> HttpResponse:
    """Downloadable 1080×1350 card: the pair-type poster plus top categories."""
    try:
        return _card_svg(request, report_provider().get_report(_scenario(request)))
    except ReportUnavailable:
        raise Http404 from None


def report_pdf(request: HttpRequest) -> HttpResponse:
    return _demo(request, "report/pdf.html")


def weights(request: HttpRequest) -> HttpResponse:
    return _demo(request, "pages/weights.html")


def question_of_day(report: Report, seed: str, today: date) -> str:
    """A new question every day, leaning on the pair's weakest spheres; both partners get the same one.
    Even days go to the four weakest spheres, odd days to the rest; each sphere walks its own pool in turn, so a
    question comes back only after its whole sphere was asked (weak ones in about 7 months, the rest in over a year).
    """
    from apps.knowledge.infrastructure.repository import KnowledgeRepository

    kb = KnowledgeRepository()
    order = [s.key for s in sorted(report.spheres, key=lambda s: s.score)]
    pools = {k: kb.series(f"QUESTION:{k}:") for k in order}
    order = [k for k in order if pools[k]]
    if not order:
        return report.daily.question
    n = (today - date(2026, 1, 1)).days + int(hashlib.sha256(seed.encode()).hexdigest()[:6], 16)
    group, k = ((order[:4] if n % 2 == 0 else order[4:]), n // 2) if order[4:] else (order, n)
    pool = pools[group[k % len(group)]]
    return pool[(k // len(group)) % len(pool)]["question"]


def _week_days(report: Report, seed: str) -> list[dict]:
    from apps.knowledge.infrastructure.repository import KnowledgeRepository

    scenario = next((s.title for s in report.psychology.scenarios if s.tone != "synergy"), "")
    return pair_week.build([(s.key, s.title, s.score) for s in report.spheres], scenario, KnowledgeRepository().series, seed)


def _week_ctx(pair: Pair | None, report: Report, side: str) -> dict:
    """«Неделя пары» for «Сегодня»: the running week, or a preview of the seven steps before it starts."""
    open_all = bool(pair) and unlocked(pair)  # type: ignore[arg-type]
    if pair and (w := pair.plan.get("week")):
        return {"week": pair_week.state(w, timezone.localdate(), side, open_all), "week_open": open_all}
    return {"week": None, "week_preview": _week_days(report, str(pair.id) if pair else "demo"), "week_open": open_all}


@require_POST
def week_start(request: HttpRequest) -> HttpResponse:
    stored = _owned_report(request, request.POST.get("rid", ""))
    pair = stored.pair
    if not pair.plan.get("week"):
        days = _week_days(report_of(stored), str(pair.id))
        pair.plan = {**pair.plan, "week": {"rid": str(stored.id), "started": timezone.localdate().isoformat(), "days": days, "done": {}}}
        pair.save(update_fields=["plan"])
        notify_partner(pair, side_of(get_owner(request), pair), "week")  # type: ignore[arg-type]
    return redirect(reverse("daily") + "#week")


@require_POST
def week_done(request: HttpRequest) -> HttpResponse:
    stored = _owned_report(request, request.POST.get("rid", ""))
    pair, side = stored.pair, side_of(get_owner(request), stored.pair)  # type: ignore[arg-type]
    w = pair.plan.get("week")
    n = int(request.POST.get("day", "0")) if request.POST.get("day", "").isdigit() else 0
    if not w:
        raise Http404
    st = pair_week.state(w, timezone.localdate(), side, unlocked(pair))
    day = next((d for d in st["days"] if d["n"] == n), None)
    if day is None or day["locked"] or day["future"]:
        return JsonResponse({"error": "closed"}, status=403)
    pair.plan = {**pair.plan, "week": pair_week.toggle(w, n, side)}
    pair.save(update_fields=["plan"])
    return JsonResponse(pair_week.state(pair.plan["week"], timezone.localdate(), side, unlocked(pair)))


def _weather(pair: Pair) -> list[dict]:
    """«Погода пары» on this week's sky; the same for everyone in a day, so it is cached per pair per day."""
    key = f"weather:{pair.id}:{timezone.localdate().isoformat()}"
    if (hit := cache.get(key)) is not None:
        return hit
    eph = SkyfieldEphemeris()
    sky = eph.chart(BirthData(timezone.localdate())).planets
    natal = [(p.name, eph.chart(BirthData(date.fromisoformat(p.birth["date"]))).planets) for p in (pair.a, pair.b)]
    result = sky_weather(sky, natal)
    cache.set(key, result, 6 * 3600)
    return result


def _talk_week() -> str:
    y, w, _ = timezone.localdate().isocalendar()
    return f"{y}-W{w:02d}"


def intimacy(request: HttpRequest) -> HttpResponse:
    """«Близость 18+»: private wishes, only matches are shown. A linked pair only — it is about the two of you."""
    owner = get_owner(request)
    pair = pairs_of(owner).exclude(partner=None).order_by("-created_at").first() if owner and owner.is_account else None
    if not pair:
        return render(request, "pages/intimacy.html", {"state": "nopair"})
    side = side_of(owner, pair)  # type: ignore[arg-type]
    rows = {r.side: r.picks for r in IntimacyAnswer.objects.filter(pair=pair)}
    if request.method == "POST":
        if request.POST.get("action") == "clear":
            IntimacyAnswer.objects.filter(pair=pair, side=side).delete()
        elif request.POST.get("action") == "date18":  # «Свидание недели» may suggest 18+ only once both switched this on
            on = pair.plan.get("date18", [])
            pair.plan = {**pair.plan, "date18": [s for s in on if s != side] if side in on else [*on, side]}
            pair.save(update_fields=["plan"])
        else:
            picks = intimacy_wishes.clean({k: request.POST.get(k, "") for k in intimacy_wishes.TITLES})
            IntimacyAnswer.objects.update_or_create(pair=pair, side=side, defaults={"picks": picks})
        return redirect("intimacy")
    mine, theirs = rows.get(side) or {}, rows.get("b" if side == "a" else "a") or {}
    on = pair.plan.get("date18", [])
    ctx = {
        "state": "ready",
        "themes": intimacy_wishes.THEMES,
        "choices": intimacy_wishes.CHOICES,
        "mine": mine,
        "partner_done": bool(theirs),
        "partner_name": pair.b.name if side == "a" else pair.a.name,
        "result": intimacy_wishes.matches(mine, theirs) if mine and theirs else None,
        "date18_mine": side in on,
        "date18_both": set(on) == {"a", "b"},  # the partner's switch alone is never shown
    }
    return render(request, "pages/intimacy.html", ctx)


def _date_idea(pair: Pair, report: Report) -> dict:
    """«Свидание недели»: weak spheres from the report, openness from both questionnaires, and 18+ only when both
    switched it on — then only from wishes both said «да» to (date_ideas.py)."""
    rows = {r.side: r.picks for r in IntimacyAnswer.objects.filter(pair=pair)}
    mutual = intimacy_wishes.both_yes(rows.get("a") or {}, rows.get("b") or {})
    close_on = bool(pair.partner_id) and set(pair.plan.get("date18", [])) == {"a", "b"}

    def open_to_new(person: Person) -> bool:
        try:
            return bool(person.answers) and psy.profile(person.answers).ocean["O"] >= date_ideas.OPEN
        except psy.IncompleteAnswers:
            return False

    weak = [s.key for s in sorted(report.spheres, key=lambda s: s.score)[:4]]
    week = date_ideas.week_no(timezone.localdate())
    idea = date_ideas.pick(week, str(pair.id), weak, open_to_new(pair.a) and open_to_new(pair.b), mutual, close_on)
    titles = {s.key: s.title for s in report.spheres}  # «про „Деньги“» on the tile: where in your report it comes from
    return {**idea, "why": next((titles[k] for k in idea["spheres"] if k in titles), "")}


def pair_calendar(request: HttpRequest) -> HttpResponse:
    """«Календарь пары»: birthdays, the day you met and its milestones, your own dates with notes — both of you see
    them, and the evening job reminds a week and a day before (dates.py)."""
    owner = get_owner(request)
    if not owner or not owner.is_account:
        return _to_login(request, "save")
    pair = pairs_of(owner).order_by("-created_at").first()
    if not pair:
        return render(request, "pages/calendar.html", {"state": "nopair"})
    side, today, error = side_of(owner, pair), timezone.localdate(), False
    if request.method == "POST":
        deleting = request.POST.get("action") == "delete"
        entry = None if deleting else pair_dates.clean(request.POST.dict(), today, side)
        if deleting or entry:
            with transaction.atomic():  # both partners edit one list: lock it so neither loses the other's date
                pair = Pair.objects.select_for_update().get(id=pair.id)
                entries = [e for e in pair.dates if e["id"] != request.POST.get("id")] if deleting else list(pair.dates)
                if entry and entry["kind"] == "met":
                    entries = [e for e in entries if e["kind"] != "met"]
                if entry and len(entries) < pair_dates.MAX_ENTRIES:
                    entries.append(entry)
                pair.dates = entries
                pair.save(update_fields=["dates"])
            return redirect("pair_calendar")
        error = True
    ctx = {
        "state": "ready",
        "events": (events := pair_dates.upcoming(today, pair_dates.people(pair), pair.dates)),
        "today_events": [e for e in events if e["in"] == 0 and e["kind"] != "holiday"],  # confetti day
        "together": (days := pair_dates.together(today, pair.dates)),
        "together_word": pair_dates.plural(days or 0, "день", "дня", "дней"),
        "road": pair_dates.road(days) if days is not None else None,
        "met": pair_dates.met_day(pair.dates),
        "side": side,
        "me_g": (pair.a if side == "a" else pair.b).gender,
        "partner_g": (pair.b if side == "a" else pair.a).gender,
        "today": today.isoformat(),
        "max_day": (today + timedelta(days=365)).isoformat(),
        "error": error,
    }
    return render(request, "pages/calendar.html", ctx, status=422 if error else 200)


def wish_map(request: HttpRequest) -> HttpResponse:
    """«Карта желаний»: your gift ideas, your partner's (reserve one quietly — they never see it), dreams for two.
    Adding is free; the quiet reservation is part of «Пара+» (wishes.py)."""
    owner = get_owner(request)
    if not owner or not owner.is_account:
        return _to_login(request, "save")
    pair = pairs_of(owner).order_by("-created_at").first()
    if not pair:
        return render(request, "pages/wishes.html", {"state": "nopair"})
    side, plus, error = side_of(owner, pair), plus_for_pair(pair), False
    if request.method == "POST":
        action = request.POST.get("action", "add")
        new = pair_wishes.clean(request.POST.dict(), side) if action == "add" else None
        if action != "add" or new:
            if action != "reserve" or plus:
                with transaction.atomic():  # both partners edit one list: lock it so neither loses the other's change
                    pair = Pair.objects.select_for_update().get(id=pair.id)
                    pair.wishes = pair_wishes.apply(pair.wishes, side, action, request.POST.get("id", ""), new)
                    pair.save(update_fields=["wishes"])
            wid = request.POST.get("id", "")
            now = next((w for w in pair.wishes if w["id"] == wid), {})
            if action == "reserve" and now.get("taken") == side:  # the box ties itself on the way back
                return redirect(reverse("wish_map") + f"?tied={wid}#theirs")
            if action == "done" and now.get("done"):  # the star lights up in the constellation
                return redirect(reverse("wish_map") + f"?lit={wid}#dreams")
            anchor = "#dreams" if request.POST.get("kind") == "dream" or action == "done" else "#theirs" if action == "reserve" else "#mine"
            return redirect(reverse("wish_map") + anchor)
        error = True
    ctx = {
        "state": "ready",
        **(seen := pair_wishes.view(pair.wishes, side)),
        "sky": pair_wishes.sky(seen["dreams"]),
        "tied": request.GET.get("tied", ""),
        "lit": request.GET.get("lit", ""),
        "kinds": {k: v for k, v in pair_wishes.KINDS.items() if k != "dream"},
        "partner_name": pair.b.name if side == "a" else pair.a.name,
        "me_g": (pair.a if side == "a" else pair.b).gender,
        "partner_g": (pair.b if side == "a" else pair.a).gender,
        "has_partner": bool(pair.partner_id),
        "plus": plus,
        "price_plus": settings.PRICE_PLUS,
        "error": error,
    }
    return render(request, "pages/wishes.html", ctx, status=422 if error else 200)


def _idea_marks(pair: Pair, side: str, celebrate: bool) -> dict:
    """«Мы сделали» for this week's «Свидание недели», and how many weeks you have both marked so far."""
    ideas = pair.plan.get("ideas", {})
    marks = ideas.get(_talk_week(), [])
    together = sum(1 for v in ideas.values() if set(v) == {"a", "b"})
    return {
        "idea_week": _talk_week(),
        "idea_mine": side in marks,
        "idea_partner": ("b" if side == "a" else "a") in marks,
        "ideas_together": together,
        "idea_stars": range(min(together, 12)),
        "idea_celebrate": celebrate and set(marks) == {"a", "b"},
    }


@require_POST
def idea_done(request: HttpRequest) -> HttpResponse:
    """«Свидание недели»: each partner marks this week's idea; it counts when both did, and the moment it does, confetti."""
    owner = get_owner(request)
    pair = pairs_of(owner).order_by("-created_at").first() if owner and owner.is_account else None
    if not pair:
        raise Http404
    side, week = side_of(owner, pair), _talk_week()  # type: ignore[arg-type]
    ideas = {k: list(v) for k, v in pair.plan.get("ideas", {}).items()}
    marks = ideas.setdefault(week, [])
    marks.remove(side) if side in marks else marks.append(side)
    pair.plan = {**pair.plan, "ideas": ideas}
    pair.save(update_fields=["plan"])
    return redirect(reverse("daily") + ("?together=1" if set(marks) == {"a", "b"} else "") + "#date-idea")


@require_POST
def talk_done(request: HttpRequest) -> HttpResponse:
    """«Как мы»: each partner marks this week's talk; it counts when both did."""
    owner = get_owner(request)
    pair = pairs_of(owner).order_by("-created_at").first() if owner and owner.is_account else None
    if not pair:
        raise Http404
    side, week = side_of(owner, pair), _talk_week()  # type: ignore[arg-type]
    talks = {k: list(v) for k, v in pair.plan.get("talk", {}).items()}
    marks = talks.setdefault(week, [])
    marks.remove(side) if side in marks else marks.append(side)
    pair.plan = {**pair.plan, "talk": talks}
    pair.save(update_fields=["plan"])
    return redirect(reverse("daily") + "#talk")


WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")


def _week_strip(pair: Pair, side: str, today: date, plus: bool) -> dict:
    """«Сегодня» opens on a week around today — three days back, three ahead, so yesterday is always there: a ring per day (half for each partner who answered the question of the day), the
    pair's dates on their days, and for a past day its question with both answers — the pair's diary, in «Пара+».
    Also «дней подряд вместе» with its weekly freeze (streak.py)."""
    sides: dict[date, set] = {}
    for d, s in DailyAnswer.objects.filter(pair=pair, day__gte=today - timedelta(days=400)).values_list("day", "side"):
        sides.setdefault(d, set()).add(s)
    both = {d for d, s in sides.items() if len(s) == 2}
    streak, freeze = pair_streak(both, today)
    start = today - timedelta(days=3)
    rows: dict[date, dict] = {}
    for r in DailyAnswer.objects.filter(pair=pair, day__gte=start, day__lt=today):
        rows.setdefault(r.day, {})[r.side] = r
    events: dict[date, list] = {}
    for e in pair_dates.upcoming(start, pair_dates.people(pair), pair.dates, horizon=6):
        events.setdefault(e["day"], []).append(e)
    other = "b" if side == "a" else "a"
    strip = []
    for i in range(7):
        d = start + timedelta(days=i)
        rs = rows.get(d, {})
        diary = {"question": rs[side].question, "mine": rs[side].text, "theirs": rs[other].text} if len(rs) == 2 else None
        strip.append({
            "day": d, "iso": d.isoformat(), "wd": WEEKDAYS[d.weekday()], "today": d == today, "past": d < today, "in": (d - today).days,
            "ring": len(sides.get(d, ())), "events": events.get(d, []), "diary": diary if plus else None, "locked": bool(diary) and not plus,
        })  # fmt: skip
    return {
        "strip": strip,
        "today_iso": today.isoformat(),
        "today_events": [e for e in events.get(today, []) if e["kind"] != "holiday"],
        "streak": streak,
        "freeze": freeze,
        "answers_together": len(both),
    }


def _tile_marks(pair: Pair, side: str, week: dict | None) -> dict:
    """Who has done this week's things, so each tile on «Сегодня» shows both partners' marks instead of a paragraph."""
    from apps.knowledge.infrastructure.repository import KnowledgeRepository

    quizzes = KnowledgeRepository().series("QUIZ:")
    done: set = set()
    if quizzes:
        key = quizzes[timezone.localdate().isocalendar().week % len(quizzes)]["key"]
        done = set(QuizAnswer.objects.filter(pair=pair, quiz_key=key).values_list("side", flat=True))
    return {
        "step": week["days"][week["today"] - 1] if week else None,
        "quiz_mine": side in done,
        "quiz_partner": ("b" if side == "a" else "a") in done,
    }


def daily(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    pair = pairs_of(owner).order_by("-created_at").first() if owner and owner.is_account else None  # anonymous: demo until signed in
    stored = latest_ready(pair) if pair else None
    today = timezone.localdate()
    if stored and pair and owner:
        report = report_of(stored)
        side = side_of(owner, pair)
        extra = {
            "stored": stored,
            "pair": pair,
            "daily_question": question_of_day(report, str(pair.id), today),
            "answers": daily_state(pair, side, today),
            "plus": plus_for_pair(pair),
            "price_deep": settings.PRICE_DEEP,
            "me_name": pair.a.name if side == "a" else pair.b.name,
            "partner_name": pair.b.name if side == "a" else pair.a.name,
            **_pair_people(request, pair),
        }
        extra["partner_av"] = extra["av_b"] if side == "a" else extra["av_a"]  # empty until the partner joins
        extra["me_av"] = extra["av_a"] if side == "a" else extra["av_b"]
        extra["me_g"], extra["partner_g"] = (pair.a.gender, pair.b.gender) if side == "a" else (pair.b.gender, pair.a.gender)
        extra["solo"] = not pair.partner_id  # tiles say what to do instead of showing a partner's marks
        extra |= _week_ctx(pair, report, side)
        talk = pair.plan.get("talk", {}).get(_talk_week(), [])
        extra |= {"weather": _weather(pair), "talk_mine": side in talk, "talk_partner": ("b" if side == "a" else "a") in talk}
        extra |= {
            "date_idea": _date_idea(pair, report),
            **_idea_marks(pair, side, request.GET.get("together") == "1"),
            **_week_strip(pair, side, today, plus_for_pair(pair)),
        }
        extra |= _tile_marks(pair, side, extra.get("week"))
        extra["tree"] = _pair_tree(pair, extra["answers_together"], extra["strip"][3]["ring"] == 2, report)  # today is the middle
        return _render_report(request, report, "pages/daily.html", reverse("stored_report", args=[stored.id]), extra)
    demo = report_provider().get_report(_scenario(request))
    demo_ctx = {"daily_question": question_of_day(demo, "demo", today), "me_g": "", **_week_ctx(None, demo, "a")}  # a guest: neutral forms
    return _render_report(request, demo, "pages/daily.html", reverse("report"), demo_ctx)


@require_POST
def daily_answer(request: HttpRequest) -> HttpResponse:
    """Save today's answer for this side of the owner's latest pair; the question is recomputed, never taken from the form."""
    owner = get_owner(request)
    pair = pairs_of(owner).order_by("-created_at").first() if owner and owner.is_account else None
    stored = latest_ready(pair) if pair else None
    text = request.POST.get("text", "").strip()[:500]
    if not (pair and stored and owner) or len(text) < 2:
        return redirect("daily")
    today = timezone.localdate()
    side = side_of(owner, pair)
    _, created = DailyAnswer.objects.update_or_create(
        pair=pair, side=side, day=today, defaults={"question": question_of_day(report_of(stored), str(pair.id), today), "text": text}
    )
    if created:
        notify_partner(pair, side, "answered")
    return redirect(reverse("daily") + "#question")


def quiz_week(request: HttpRequest) -> HttpResponse:
    """Quiz of the week (Пара+): each partner answers about themselves; matches show once both have answered."""
    from apps.knowledge.infrastructure.repository import KnowledgeRepository

    owner = get_owner(request)
    pair = pairs_of(owner).order_by("-created_at").first() if owner and owner.is_account else None
    if not pair or not owner:
        return _to_login(request, "save")
    quizzes = KnowledgeRepository().series("QUIZ:")
    if not quizzes:
        raise Http404
    quiz = quizzes[timezone.localdate().isocalendar().week % len(quizzes)]
    side = side_of(owner, pair)
    me, partner = (pair.a, pair.b) if side == "a" else (pair.b, pair.a)
    ctx = {"quiz": quiz, "pair": pair, "plus": plus_for_pair(pair), "has_partner": bool(pair.partner_id), "price_plus": settings.PRICE_PLUS}
    ctx |= {"me_g": me.gender, "partner_g": partner.gender}  # «Побыть одному(ой)»: own options in my form, guesses in theirs
    if request.method == "POST" and ctx["plus"]:
        try:
            picks = [int(request.POST[f"q{i}"]) for i in range(len(quiz["items"]))]
            guesses = [int(request.POST[f"g{i}"]) for i in range(len(quiz["items"]))] if ctx["has_partner"] else []
        except (KeyError, ValueError):
            return render(request, "pages/quiz_week.html", {**ctx, "error": True}, status=422)
        fits = lambda row: all(0 <= p < len(item["options"]) for p, item in zip(row, quiz["items"], strict=False))  # noqa: E731
        if fits(picks) and fits(guesses):
            _, created = QuizAnswer.objects.update_or_create(
                pair=pair, side=side, quiz_key=quiz["key"], defaults={"picks": picks, "guesses": guesses}
            )
            if created:
                notify_partner(pair, side, "quiz")
        return redirect("quiz_week")
    rows = {r.side: r for r in QuizAnswer.objects.filter(pair=pair, quiz_key=quiz["key"])}
    me_row, them_row = rows.get(side), rows.get("b" if side == "a" else "a")
    mine, theirs = (me_row.picks if me_row else None), (them_row.picks if them_row else None)
    if mine and theirs:
        my_guess, their_guess = me_row.guesses or [None] * len(mine), them_row.guesses or [None] * len(theirs)  # type: ignore[union-attr]
        results = [
            {
                "q": item["q"],
                "mine": item["options"][m],
                "theirs": item["options"][t],
                "same": m == t,
                "i_guessed": g == t,
                "they_guessed": h == m,
            }
            for item, m, t, g, h in zip(quiz["items"], mine, theirs, my_guess, their_guess, strict=True)
        ]
        ctx |= {"results": results, "match": round(100 * sum(r["same"] for r in results) / len(results))}
        if me_row.guesses and them_row.guesses:  # type: ignore[union-attr]
            ctx |= {"i_guessed": sum(r["i_guessed"] for r in results), "they_guessed": sum(r["they_guessed"] for r in results)}
    ctx |= {"mine": mine, "partner_done": bool(theirs), "me_name": me.name, "partner_name": partner.name}
    return render(request, "pages/quiz_week.html", ctx)


def pair_ready(request: HttpRequest) -> HttpResponse:
    return _demo(request, "pages/pair_ready.html")


def _parse_date(raw: str | None) -> date | None:
    try:
        d = date.fromisoformat(raw or "")
    except ValueError:
        return None
    return d if date(1900, 1, 1) <= d <= date.today() else None


def _parse_time(raw: str | None) -> time | None:
    try:
        return time.fromisoformat(raw) if raw else None
    except ValueError:
        return None


@require_POST
def quick_result(request: HttpRequest) -> HttpResponse:
    da, db = _parse_date(request.POST.get("date_a")), _parse_date(request.POST.get("date_b"))
    if not (da and db):
        return render(request, "partials/quick_result.html", {"errors": {"a": not da, "b": not db}})
    request.session["quick_dates"] = [da.isoformat(), db.isoformat()]  # «Полный разбор» starts from these
    return render(request, "partials/quick_result.html", {"q": report_provider().quick_result(da, db)})


def _wizard_ctx() -> dict:
    return {"modes": WIZARD_MODES, "quizzes": WIZARD_QUIZZES, "cities": CITIES}


def _place_from(request: HttpRequest, prefix: str) -> tuple[str | None, tuple[float, float, str] | None]:
    """Birthplace from a form: the name and, if picked on the map or found by name, its coordinates and zone."""
    text = request.POST.get(f"{prefix}place", "").strip()[:120] or None
    point = places.coords(request.POST.get(f"{prefix}lat"), request.POST.get(f"{prefix}lon"), request.POST.get(f"{prefix}tz"))
    if text and not point and (found := places.resolve(text)):
        point = (found.lat, found.lon, found.tz)
    return text, point


@cache_control(public=True, max_age=86400)
def place_search(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"items": [places.as_dict(p) for p in places.search(request.GET.get("q", "")[:60])]})


def _floats(request: HttpRequest, *names: str) -> list[float] | None:
    try:
        vals = [float(request.GET.get(n, "")) for n in names]
    except ValueError:
        return None
    return vals if all(-180 <= v <= 180 for v in vals) else None


@cache_control(public=True, max_age=86400)
def place_near(request: HttpRequest) -> JsonResponse:
    pt = _floats(request, "lat", "lon")
    found = places.nearest(*pt) if pt and abs(pt[0]) <= 90 else None
    return JsonResponse({"place": places.as_dict(found[0]), "km": round(found[1], 1)} if found else {"place": None})


@cache_control(public=True, max_age=86400)
def place_box(request: HttpRequest) -> JsonResponse:
    box = _floats(request, "w", "s", "e", "n")
    if not box:
        return JsonResponse({"items": []})
    limit = min(int(request.GET.get("limit", "160")) if request.GET.get("limit", "").isdigit() else 160, 300)
    w, s, e, n = box
    return JsonResponse({"items": [places.as_dict(p) for p in places.in_box(w, s, e, n, limit=limit)]})


def _own_pair(request: HttpRequest, pair_id: str | None) -> Pair | None:
    owner = get_owner(request)
    if not (owner and pair_id):
        return None
    try:
        return Pair.objects.select_related("a", "b").filter(id=pair_id, owner=owner).first()
    except ValidationError:
        return None


def _person_prefill(p: Person) -> dict:
    b = p.birth or {}
    geo = {k: b[k] for k in ("lat", "lon", "tz") if b.get(k) is not None}
    return {"name": p.name, "date": b.get("date") or "", "time": b.get("time") or "", "place": b.get("place") or "", "noTime": False, **geo}


def _wizard_prefill(request: HttpRequest) -> dict | None:
    """What the person already told us: the pair being made more precise, or the dates from the quick check."""
    if pair := _own_pair(request, request.GET.get("pair")):
        return {"pair": str(pair.id), "a": _person_prefill(pair.a), "b": _person_prefill(pair.b), "partner_linked": bool(pair.partner_id)}
    if dates := request.session.get("quick_dates"):
        return {"a": {"date": dates[0]}, "b": {"date": dates[1]}}
    return None


def wizard(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        prefill = _wizard_prefill(request)
        mode = request.GET.get("mode") or ("extended" if prefill and prefill.get("pair") else "quick")
        return render(request, "pages/wizard.html", {**_wizard_ctx(), "mode": mode, "prefill": prefill})
    da, db = _parse_date(request.POST.get("a_date")), _parse_date(request.POST.get("b_date"))
    if not (da and db):
        return render(request, "pages/wizard.html", {**_wizard_ctx(), "error": True}, status=422)
    mode = request.POST.get("mode", "quick") if request.POST.get("mode") in {"quick", "extended", "deep"} else "quick"
    owner = get_owner(request) or Owner.objects.create()

    def person(prefix: str, day: date) -> dict:
        return {
            "name": request.POST.get(f"{prefix}_name", "").strip()[:80],
            "gender": g if (g := request.POST.get(f"{prefix}_gender", "")) in ("f", "m") else "",
            "date": day,
            "time": _parse_time(request.POST.get(f"{prefix}_time")),
            **dict(zip(("place", "point"), _place_from(request, f"{prefix}_"), strict=True)),
        }

    pair = _own_pair(request, request.POST.get("pair"))
    if pair:  # the same pair, more precise: answers, plan and partner link stay
        update_person(pair.a, person("a", da))
        if not pair.partner_id:  # a linked partner keeps their own data (they edit it from their «Профиль»)
            update_person(pair.b, person("b", db))
        pair.mode = mode
        pair.save(update_fields=["mode"])
    else:
        pair = create_pair(owner, person("a", da), person("b", db), mode)
    request.session.pop("quick_dates", None)
    target = reverse("person_quiz", args=[pair.a.id]) if mode == "deep" else reverse("generating") + f"?r={request_report(pair).id}"
    return remember_owner(request, redirect(target), owner)


def generating(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/generating.html", {"steps": report_provider().generation_steps(), "rid": request.GET.get("r", "")})


def generating_status(request: HttpRequest) -> HttpResponse:
    steps = report_provider().generation_steps()
    try:
        step = max(0, int(request.GET.get("step", 0)))
    except ValueError:
        step = 0
    rid = request.GET.get("r", "")
    stored = StoredReport.objects.filter(id=rid).first() if rid else None
    if step >= len(steps):
        owner = get_owner(request)
        if stored and stored.status == StoredReport.Status.PENDING:
            step = len(steps) - 1  # keep the last step spinning until the worker finishes
        elif stored and stored.status == StoredReport.Status.READY and not (owner and owner.is_account):
            # ready, no profile yet: a glimpse of the result, then one step — save it, which creates the profile
            if not owner or owner.id not in (stored.pair.owner_id, stored.pair.partner_id):
                raise Http404
            nxt = reverse("stored_report", args=[stored.id]) + "?reveal=1"
            ctx = {"teaser": report_of(stored), "save_query": urlencode({"sheet": "1", "why": "save", "next": nxt})}
            return render(request, "partials/generation_steps.html", ctx)
        else:
            resp = HttpResponse(status=204)
            resp["HX-Redirect"] = (reverse("stored_report", args=[stored.id]) if stored else reverse("report")) + "?reveal=1"
            return resp
    ctx = {"steps": steps, "step": step, "progress": round(100 * step / len(steps)), "rid": rid}
    return render(request, "partials/generation_steps.html", ctx)


# ── stored reports (owner-only) ───────────────────────────────────────────
def _owned_report(request: HttpRequest, rid) -> StoredReport:
    owner = get_owner(request)
    stored = StoredReport.objects.select_related("pair").filter(id=rid).first()
    if not stored or not owner or owner.id not in (stored.pair.owner_id, stored.pair.partner_id):
        raise Http404  # the creator and the joined partner only
    return stored


def _unlock_items(report: Report) -> list[tuple[str, str, str]]:
    """What the full report adds for this very pair, from its own results: (icon, title, detail)."""
    items = []
    spheres = sorted(report.spheres, key=lambda s: s.score)
    if spheres:
        weak = " и ".join(f"«{s.title}»" for s in spheres[:2])
        items.append(
            (
                "book-open",
                f"Все {len(spheres)} сфер целиком",
                f"Сильнее всего у вас — «{spheres[-1].title}», зона внимания — {weak}: почему так и что с этим делать.",
            )
        )
    scen = report.psychology.scenarios
    if scen:
        more = f" и ещё {len(scen) - 1}" if len(scen) > 1 else ""
        items.append(
            (
                "users",
                f"«{scen[0].title}»{more}",
                "Ваши повторяющиеся сценарии в спорах и близости — и как из них выходить, со ссылками на исследования.",
            )
        )
    elif not report.psychology.available:
        items.append(("brain", "Научный слой", "После анкет обоих: привязанность, черты характера и стиль конфликтов каждого."))
    links = len(report.astrology.all_aspects or report.astrology.aspects)
    if links:
        items.append(
            (
                "orbit",
                f"{links} связей между вашими картами",
                "Синастрия, наложение домов и композит — с графиками и объяснением каждой связи.",
            )
        )
    items.append(
        (
            "calendar-days",
            "Неделя пары: 7 шагов",
            "Разговоры и упражнения для ваших слабых сфер — вы отмечаете их вдвоём во вкладке «Сегодня».",
        )
    )
    items.append(("file-down", "PDF и доступ партнёру", "Одна покупка — разбор открывается вам обоим."))
    return items


def _stored(request: HttpRequest, rid, template: str, **ctx) -> HttpResponse:
    owner = get_owner(request)
    if owner and not owner.is_account:
        return _to_login(request, "save")
    stored = _owned_report(request, rid)
    if stored.status == StoredReport.Status.PENDING:
        return redirect(reverse("generating") + f"?r={stored.id}")
    if stored.status == StoredReport.Status.FAILED:
        return render(request, "report/error.html", {"retry_url": reverse("retry_report", args=[stored.id])}, status=503)
    pair = stored.pair
    locked = not unlocked(pair)
    if locked and (ctx.get("tab") in LAYER_TABS or template == "report/pdf.html"):
        template = "report/locked.html"
        ctx["locked_title"] = f"{LAYER_TABS[ctx['tab']][0] if ctx.get('tab') in LAYER_TABS else 'PDF'} — в полном разборе"
    extra = {
        "stored": stored,
        "locked": locked,
        "price_deep": settings.PRICE_DEEP,
        "unlock_items": _unlock_items(report_of(stored)) if locked else [],
        "gift_code": request.session.get("gift_code", "") if locked else "",  # a gift waiting for this pair
        "quiz_url": reverse("person_quiz", args=[pair.a_id]),
        "invite_url": reverse("invite", args=[stored.id]),
        "share_url": request.build_absolute_uri(reverse("public_share", args=[share_token(stored)])),
    }
    if owner and pair.owner_id == owner.id:
        extra["upgrade_url"] = reverse("wizard") + "?" + urlencode({"mode": "extended", "pair": str(pair.id)})
    extra |= _pair_people(request, pair)
    return _render_report(request, report_of(stored), template, reverse("stored_report", args=[stored.id]), extra, **ctx)


def stored_report(request: HttpRequest, rid) -> HttpResponse:
    return _stored(request, rid, "report/dashboard.html", tab="overview", reveal=request.GET.get("reveal") == "1")


def stored_tab(request: HttpRequest, rid, tab: str) -> HttpResponse:
    if tab == "share":
        return _stored(request, rid, "report/share.html", tab="share")
    if tab in ("pdf", "weights"):
        return _stored(request, rid, "report/pdf.html" if tab == "pdf" else "pages/weights.html")
    if tab not in REPORT_TABS and tab not in LAYER_TABS:
        raise Http404
    return _stored(request, rid, f"report/{tab}.html", tab=tab, deal=tab == "tarot")


def stored_card(request: HttpRequest, rid) -> HttpResponse:
    return _card_svg(request, report_of(_owned_report(request, rid)))


@require_POST
def retry_report(request: HttpRequest, rid) -> HttpResponse:
    stored = _owned_report(request, rid)
    stored.delete()
    return redirect(reverse("generating") + f"?r={request_report(stored.pair).id}")


def public_share(request: HttpRequest, token: str) -> HttpResponse:
    stored = from_share_token(token)
    if not stored:
        raise Http404
    r = report_of(stored)
    return render(request, "pages/public_share.html", {"r": r, "a": r.partners[0], "b": r.partners[1]})


# ── questionnaires ────────────────────────────────────────────────────────
def _quiz_ctx(gender: str = "") -> dict:
    """Questionnaire sections; «Я … сам(а)» in the form of the person answering when we know it."""
    from apps.core.domain.names import agree

    items = lambda s: [{"id": i.id, "text": agree(i.text, gender)} for i in s.items]  # noqa: E731
    return {"sections": [{"title": s.title, "hint": s.hint, "items": items(s)} for s in SECTIONS], "likert": LIKERT}


def quiz(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/quiz.html", {**_quiz_ctx(), "submit_url": ""})


def _save_answers(request: HttpRequest, person: Person) -> dict[str, int] | None:
    try:
        raw = json.loads(request.POST.get("answers", "{}"))
        answers = {k: int(v) for k, v in raw.items() if k in ITEMS}
        psy.profile(answers)  # validates scale and completeness
    except (ValueError, TypeError, json.JSONDecodeError, psy.IncompleteAnswers):
        return None
    if len(answers) != len(ITEMS):
        return None
    person.answers, person.answered_at = answers, timezone.now()
    person.save(update_fields=["answers", "answered_at"])
    return answers


def person_quiz(request: HttpRequest, pid) -> HttpResponse:
    person, _ = _editable_person(request, pid)
    owner = get_owner(request)
    if request.method == "POST":
        if _save_answers(request, person) is None:
            return HttpResponse("answers incomplete", status=422)
        pair = pairs_of(owner).filter(models.Q(a=person) | models.Q(b=person)).first()  # type: ignore[arg-type]
        if pair is None:
            return redirect("history")
        if pair.mode == "deep" and person == pair.a and not pair.b.answers:
            return redirect(reverse("invite_new", args=[pair.id]))
        return redirect(reverse("generating") + f"?r={request_report(pair).id}")
    return render(request, "pages/quiz.html", {**_quiz_ctx(person.gender), "person": person, "submit_url": request.path})


# ── pair mode: the partner joins from their own account (ADR-0010) ────────
def invite(request: HttpRequest, rid) -> HttpResponse:
    stored = _owned_report(request, rid)
    if stored.pair.owner_id != get_owner(request).id:  # type: ignore[union-attr]
        raise Http404
    return _invite_page(request, stored.pair)


def invite_new(request: HttpRequest, pair_id) -> HttpResponse:
    owner = get_owner(request)
    pair = Pair.objects.filter(id=pair_id, owner=owner).first() if owner else None
    if not pair:
        raise Http404
    return _invite_page(request, pair)


def _to_login(request: HttpRequest, why: str) -> HttpResponse:
    return redirect(reverse("login") + "?" + urlencode({"next": request.get_full_path(), "why": why}))


def _invite_page(request: HttpRequest, pair: Pair) -> HttpResponse:
    if not get_owner(request).is_account:  # type: ignore[union-attr]
        return _to_login(request, "invite")  # inviting needs an account, so both sides can find the pair later
    if request.method == "POST":
        invite_code(pair, fresh=True)  # the old code and link stop working
    code = invite_code(pair)
    return render(
        request,
        "pages/pair_invite.html",
        {
            "invite_link": request.build_absolute_uri(reverse("join", args=[code])),
            "code": code,
            "partner": pair.b,
            "pair": pair,
            "waiting_url": reverse("pair_status", args=[pair.id]),
        },
    )


def pair_status(request: HttpRequest, pair_id) -> HttpResponse:
    owner = get_owner(request)
    pair = Pair.objects.filter(id=pair_id, owner=owner).first() if owner else None
    if not pair:
        raise Http404
    if pair.b.answers:
        return redirect(reverse("generating") + f"?r={request_report(pair).id}")
    return render(request, "pages/pair_waiting.html", {"partner": pair.b, "pair": pair})


def _invite_info(request: HttpRequest, pair: Pair) -> dict:
    code = invite_code(pair)
    return {"pair": str(pair.id), "code": code, "link": request.build_absolute_uri(reverse("join", args=[code])), "name": pair.b.name}


def _pair_people(request: HttpRequest, pair: Pair) -> dict:
    """Both partners' avatars, and the invite while the creator still waits for the partner to join."""
    owner = get_owner(request)
    ctx: dict = {
        "av_a": (pair.owner.avatar if pair.owner else "") or "sun",
        "av_b": (pair.partner.avatar or "moon") if pair.partner else "",
        "b_joined": bool(pair.partner_id),
        "my_side": side_of(owner, pair) if owner else "a",
        "invite": None,
    }
    if owner and owner.is_account and pair.owner_id == owner.id and not pair.partner_id:
        ctx["invite"] = _invite_info(request, pair)
    return ctx


@require_POST
def profile_save(request: HttpRequest) -> HttpResponse:
    """Name and avatar from the cabinet."""
    owner = get_owner(request)
    if not owner:
        raise Http404
    if (av := request.POST.get("avatar", "")) in AVATARS:
        owner.avatar = av
    if "name" in request.POST:
        owner.name = request.POST["name"].strip()[:60]
    owner.save(update_fields=["avatar", "name"])
    return redirect(_next_url(request) or reverse("account"))


NOTES_KEEP, NUDGES_A_DAY, THANKS_MAX = 60, 3, 140


def _pair_tree(pair: Pair, answers: int, watered: bool, report: Report | None) -> dict:
    """«Наше дерево»: grown by what you did together, with a head start for months together and a species from the
    pair's dynamic — compatibility picks the kind of tree, never its size (tree.py)."""
    known = pair_dates.together(timezone.localdate(), pair.dates)
    dates_n = sum(1 for v in pair.plan.get("ideas", {}).values() if set(v) == {"a", "b"})
    dreams = sum(1 for w in pair.wishes if w["kind"] == "dream" and w["done"])
    kind = report.pair_type.dynamic if report else "complement"
    return pair_tree.grow(answers, dates_n, dreams, watered, months=(known or 0) // 30, kind=kind)


def together(request: HttpRequest) -> HttpResponse:
    """«Вдвоём»: your shared space — the tree you grow by doing things together, «Думаю о тебе», a thank-you, what your
    partner did lately, and everything that is «ours» as tiles. Before the partner joins it is the invite."""
    owner = get_owner(request)
    pair = pairs_of(owner).order_by("-created_at").first() if owner else None
    if not owner or not owner.is_account or not pair:  # without an account it is a preview: what is here and how to begin
        return render(
            request,
            "pages/together_preview.html",
            {"has_report": bool(pair and latest_ready(pair)), "account": bool(owner and owner.is_account)},
        )
    if not pair.partner_id:  # step one of the path: invite the partner
        return redirect("invite_new", pair_id=pair.id)
    side, today = side_of(owner, pair), timezone.localdate()  # type: ignore[arg-type]
    other = "b" if side == "a" else "a"
    sides: dict[date, set] = {}
    for d, s in DailyAnswer.objects.filter(pair=pair).values_list("day", "side"):
        sides.setdefault(d, set()).add(s)
    both = {d for d, s in sides.items() if len(s) == 2}
    streak, freeze = pair_streak(both, today)
    dates_n = sum(1 for v in pair.plan.get("ideas", {}).values() if set(v) == {"a", "b"})
    dreams_done = sum(1 for w in pair.wishes if w["kind"] == "dream" and w["done"])
    partner_name = pair.b.name if side == "a" else pair.a.name
    feed = [{"at": datetime.fromisoformat(n["at"]), "kind": n["kind"], "text": n.get("text", "")} for n in pair.notes if n["by"] == other]
    feed += [
        {"at": a.created_at, "kind": "answer", "text": ""}
        for a in DailyAnswer.objects.filter(pair=pair, side=other).order_by("-created_at")[:1]
    ]
    feed += [
        {"at": q.created_at, "kind": "quiz", "text": ""}
        for q in QuizAnswer.objects.filter(pair=pair, side=other).order_by("-created_at")[:1]
    ]
    soon = pair_dates.upcoming(today, pair_dates.people(pair), pair.dates, horizon=60)
    ctx = {
        "pair": pair,
        "stored": latest_ready(pair),
        "me_name": pair.a.name if side == "a" else pair.b.name,
        "partner_name": partner_name,
        "known": pair_dates.together(today, pair.dates),
        "met": pair_dates.met_day(pair.dates),
        "streak": streak,
        "freeze": freeze,
        "answers_together": len(both),
        "dates_together": dates_n,
        "dreams_done": dreams_done,
        "tree": _pair_tree(pair, len(both), today in both, report := report_of(stored) if (stored := latest_ready(pair)) else None),
        "report": report,
        "dynamic": DYNAMICS[report.pair_type.dynamic].title if report and report.pair_type.dynamic in DYNAMICS else "",
        "feed": sorted(feed, key=lambda f: f["at"], reverse=True)[:6],
        "next_date": next((e for e in soon if e["kind"] != "holiday"), None),
        "partner_ideas": len(pair_wishes.view(pair.wishes, side)["theirs"]),
        "weather": _weather(pair),
        "sent": request.GET.get("sent", ""),
        "path": _pair_path(owner, pair, len(both), latest_ready(pair)),  # type: ignore[arg-type]
        "today_mine": side in sides.get(today, ()),
        "today_partner": other in sides.get(today, ()),
        **_pair_people(request, pair),
    }
    ctx["me_av"], ctx["partner_av"] = (ctx["av_a"], ctx["av_b"]) if side == "a" else (ctx["av_b"], ctx["av_a"])
    ctx["me_g"], ctx["partner_g"] = (pair.a.gender, pair.b.gender) if side == "a" else (pair.b.gender, pair.a.gender)
    return render(request, "pages/together.html", ctx)


def _note(request: HttpRequest, kind: str, text: str = "") -> HttpResponse:
    """«Думаю о тебе» / «Спасибо за…»: a few a day, kept encrypted on the pair, and the partner hears about it in
    neutral words — what was said is only shown inside the app."""
    owner = get_owner(request)
    pair = pairs_of(owner).exclude(partner=None).order_by("-created_at").first() if owner and owner.is_account else None
    if not pair:
        raise Http404
    side = side_of(owner, pair)  # type: ignore[arg-type]
    if (
        not cache.add(f"{kind}:{pair.id}:{side}:{timezone.localdate()}", 1, 26 * 3600)
        and cache.incr(f"{kind}:{pair.id}:{side}:{timezone.localdate()}") > NUDGES_A_DAY
    ):
        return redirect(reverse("pair_invite") + "?sent=enough")
    with transaction.atomic():
        pair = Pair.objects.select_for_update().get(id=pair.id)
        pair.notes = [*pair.notes, {"kind": kind, "by": side, "text": text, "at": timezone.now().isoformat()}][-NOTES_KEEP:]
        pair.save(update_fields=["notes"])
    notify_partner(pair, side, kind)
    return redirect(reverse("pair_invite") + f"?sent={kind}")


@require_POST
def nudge(request: HttpRequest) -> HttpResponse:
    return _note(request, "nudge")


@require_POST
def thanks(request: HttpRequest) -> HttpResponse:
    text = " ".join(request.POST.get("text", "").split())[:THANKS_MAX]
    if len(text) < 2:
        return redirect(reverse("pair_invite") + "#thanks")
    return _note(request, "thanks", text)


def join_by_code(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        pair = pair_by_code(request.POST.get("code", ""))
        if pair and pair.invite_code:
            return redirect("join", code=pair.invite_code)
        return render(request, "pages/join.html", {"state": "enter", "error": True}, status=404)
    return render(request, "pages/join.html", {"state": "enter"})


def join(request: HttpRequest, code: str) -> HttpResponse:
    pair = pair_by_code(code)
    if not pair:
        return render(request, "pages/join.html", {"state": "enter", "error": True}, status=404)
    owner = get_owner(request)
    ctx = {"pair": pair, "inviter": pair.a, "partner": pair.b}
    if owner and owner.id == pair.owner_id:
        return render(request, "pages/join.html", {**ctx, "state": "own"})
    if pair.partner_id and (not owner or pair.partner_id != owner.id):
        return render(request, "pages/join.html", {**ctx, "state": "taken"}, status=410)
    signed_in = bool(owner and owner.is_account)
    if not owner or pair.partner_id != owner.id:
        # one flow, like an app invite: agree and join; without a profile the sign-in card follows on the same page,
        # and signing in finishes the join (_sign_in) — no coming back to this page to press «join» again
        consent_missing = request.method == "POST" and request.POST.get("consent") != "on"
        if request.method == "POST" and request.POST.get("action") == "accept" and not consent_missing:
            if signed_in:
                _join(pair, owner)  # type: ignore[arg-type]
            else:
                request.session["join_code"] = pair.invite_code  # the consent is given; the join waits for the profile
            return redirect("join", code=pair.invite_code)
        if not signed_in and request.session.get("join_code") == pair.invite_code:
            login_query = urlencode({"sheet": "1", "why": "join", "next": request.path})
            return render(request, "pages/join.html", {**ctx, "state": "signin", "login_query": login_query})
        return render(request, "pages/join.html", {**ctx, "state": "accept", "signed_in": signed_in, "consent_missing": consent_missing})
    if not pair.b.answers:  # the partner fills in their own questionnaire
        if request.method == "POST":
            if _save_answers(request, pair.b) is None:
                return HttpResponse("answers incomplete", status=422)
            return redirect(reverse("generating") + f"?r={request_report(pair).id}")
        return render(request, "pages/quiz.html", {**_quiz_ctx(), "person": pair.b, "submit_url": request.path, "joining": True})
    stored = latest_ready(pair)
    return redirect(reverse("stored_report", args=[stored.id]) if stored else reverse("generating") + f"?r={request_report(pair).id}")


def _join(pair: Pair, owner: Owner) -> None:
    pair.partner, pair.joined_at = owner, timezone.now()
    pair.save(update_fields=["partner", "joined_at"])
    if not owner.name and pair.b.name:  # the profile is named from the invite, not asked again
        owner.name = pair.b.name[:60]
        owner.save(update_fields=["name"])
    notify_partner(pair, "b", "joined")
    grant_trial(pair)


def pair_story(request: HttpRequest, pair_id) -> HttpResponse:
    """«История пары»: the timeline, how the spheres moved, and a nudge to look again after three months."""
    owner = get_owner(request)
    pair = pairs_of(owner).select_related("a", "b").filter(id=pair_id).first() if owner and owner.is_account else None
    if not pair:
        raise Http404
    ready = list(pair.reports.filter(status=StoredReport.Status.READY).order_by("created_at"))
    snaps = [s.snapshot or {} for s in ready]
    rows = [
        {"created_at": s.created_at, "score": n["total_score"], "pair_type": n["pair_type"]["name"]}
        for s, n in zip(ready, snaps, strict=True)
    ]
    opened = (
        Purchase.objects.filter(pair=pair, kind="deep", status="succeeded").order_by("paid_at").values_list("paid_at", flat=True).first()
    )
    side = side_of(owner, pair)  # type: ignore[arg-type]
    ctx = {
        "pair": pair,
        "events": story.events(rows, pair.joined_at, pair.plan.get("week"), opened),
        "changes": story.changes(snaps[0].get("spheres", []), snaps[-1].get("spheres", [])) if len(snaps) > 1 else [],
        "scores": [r["score"] for r in rows],
        "recheck": bool(ready) and story.recheck_due(ready[-1].created_at, timezone.now()),
        "quiz_url": reverse("person_quiz", args=[pair.a_id if side == "a" else pair.b_id]),
        "latest": ready[-1] if ready else None,
    }
    return render(request, "pages/story.html", ctx)


@require_POST
def unlink_partner(request: HttpRequest, pair_id) -> HttpResponse:
    owner = get_owner(request)
    pair = pairs_of(owner).filter(id=pair_id).first() if owner else None
    if not pair:
        raise Http404
    with transaction.atomic():
        # what the partner put in themselves leaves with them: questionnaire, daily and quiz answers; the report is
        # recounted without them. Birth data stays — the creator entered it to make the pair in the first place.
        had_answers = bool(pair.b.answers)
        pair.b.answers = None
        pair.b.save(update_fields=["answers"])
        DailyAnswer.objects.filter(pair=pair, side="b").delete()
        QuizAnswer.objects.filter(pair=pair, side="b").delete()
        IntimacyAnswer.objects.filter(pair=pair, side="b").delete()
        pair.dates = [e for e in pair.dates if e.get("by") != "b"]  # the partner's calendar dates go too
        pair.wishes = pair_wishes.leave(pair.wishes, "b")  # their ideas and dreams, and their quiet reservations
        pair.notes = [n for n in pair.notes if n["by"] != "b"]  # their «Думаю о тебе» and thank-yous
        pair.plan = {**pair.plan, "date18": [s for s in pair.plan.get("date18", []) if s != "b"]}
        pair.partner = None
        pair.save(update_fields=["partner", "dates", "wishes", "notes", "plan"])
        invite_code(pair, fresh=True)
        if had_answers:
            pair.reports.all().delete()
            request_report(pair)
    return redirect("history")


# ── accounts: sign in by an emailed code, no passwords (ADR-0010) ─────────
def _next_url(request: HttpRequest) -> str:
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    return nxt if url_has_allowed_host_and_scheme(nxt, {request.get_host()}, require_https=request.is_secure()) else reverse("account")


LOGIN_TITLE = {
    "save": "Сохраните разбор — это и есть ваш профиль",
    "profile": "Вы ещё не вошли",
    "join": "Последний шаг — вход",
    "gift": "Вам подарили полный разбор",
}
LOGIN_WHY = {
    "save": "Разбор не потеряется, откроется с любого устройства, и партнёра можно будет позвать. Пароль не нужен — пришлём код на почту.",
    "profile": "Без пароля — пришлём код. Имя возьмём из вашего разбора, аватар выберете потом. Пока вы не вошли, разборы хранятся только в этом браузере 7 дней.",
    "invite": "Чтобы пригласить партнёра, войдите по почте: так вы оба найдёте вашу пару с любого устройства.",
    "join": "После входа вы сразу окажетесь в паре — так вы оба найдёте её с любого устройства. Пароль не нужен.",
    "pay": "Войдите по почте: туда придёт чек, а покупка откроется с любого устройства. Пароль не нужен.",
    "gift": "Войдите — и подарок откроет разбор вашей пары целиком, вам обоим. Пароль не нужен.",
}


def _sign_in(request: HttpRequest, *args, **kwargs) -> Owner:
    """sign_in, then what the person was in the middle of: joining a pair they had already agreed to."""
    account = sign_in(get_owner(request), *args, **kwargs)
    code = request.session.pop("join_code", None)
    pair = pair_by_code(code) if code else None
    if pair and not pair.partner_id and pair.owner_id != account.id:
        _join(pair, account)
    return account


def _in_sheet(request: HttpRequest) -> bool:
    return (request.POST.get("sheet") or request.GET.get("sheet")) == "1"


def _login_render(request: HttpRequest, ctx: dict, status: int = 200) -> HttpResponse:
    """The full /login/ page, or just the card when the sign-in sheet asked for it (htmx swaps only 2xx answers)."""
    if _in_sheet(request):
        return render(request, "components/login_card.html", {**ctx, "sheet": True})
    return render(request, "pages/login.html", ctx, status=status)


def login(request: HttpRequest) -> HttpResponse:
    why = request.POST.get("why") or request.GET.get("why", "")
    ctx = {
        "next": _next_url(request),
        "why": LOGIN_WHY.get(why, ""),
        "why_key": why if why in LOGIN_WHY else "",
        "title": LOGIN_TITLE.get(why, ""),
        "providers": oauth.enabled(),
        "telegram_bot": settings.TELEGRAM_BOT_NAME,
    }
    if request.method != "POST":
        return _login_render(request, {**ctx, "step": "email"})
    email = request.POST.get("email", "").strip()
    try:
        validate_email(email)
    except ValidationError:
        return _login_render(request, {**ctx, "step": "email", "email": email, "error": True}, status=422)
    code = issue_login_code(email)
    if code:
        link = (
            request.build_absolute_uri(reverse("login_link", args=[login_link_token(email, code)])) + "?" + urlencode({"next": ctx["next"]})
        )
        send_mail(
            f"Код входа в Duoverse: {code}",
            f"Ваш код: {code}\n\nИли откройте ссылку на этом же устройстве (действует 15 минут):\n{link}\n\n"
            "Если вы не запрашивали вход, просто удалите это письмо.",
            None,
            [email],
        )
    request.session["login_hash"] = email_hash(email)
    return _login_render(request, {**ctx, "step": "code", "email": email, "throttled": code is None})


@require_POST
def login_verify(request: HttpRequest) -> HttpResponse:
    h = request.session.get("login_hash", "")
    email = check_login_code(h, request.POST.get("code", "")) if h else None
    if not email:
        ctx = {"next": _next_url(request), "step": "code", "email": request.POST.get("email", ""), "error": True}
        return _login_render(request, ctx, status=422)
    return _finish_login(request, email)


def login_link(request: HttpRequest, token: str) -> HttpResponse:
    parsed = from_login_link(token)
    email = check_login_code(*parsed) if parsed else None
    if not email:
        return render(request, "pages/login.html", {"next": _next_url(request), "step": "email", "expired": True}, status=410)
    return _finish_login(request, email)


def _finish_login(request: HttpRequest, email: str) -> HttpResponse:
    account = _sign_in(request, email)
    request.session.pop("login_hash", None)
    if _in_sheet(request):  # the sheet closes into the page the person was on (or where the action leads)
        done = HttpResponse(status=204)
        done["HX-Redirect"] = _next_url(request)
        return remember_owner(request, done, account)
    return remember_owner(request, redirect(_next_url(request)), account)


def oauth_start(request: HttpRequest, provider: str) -> HttpResponse:
    if provider not in oauth.enabled() or provider == "telegram":
        raise Http404
    state = secrets.token_urlsafe(32)
    verifier, challenge = oauth.pkce()
    request.session["oauth"] = {"provider": provider, "state": state, "verifier": verifier, "next": _next_url(request)}
    return redirect(oauth.authorize_url(provider, request.build_absolute_uri(reverse("oauth_callback", args=[provider])), state, challenge))


def oauth_callback(request: HttpRequest, provider: str) -> HttpResponse:
    pending = request.session.pop("oauth", None)
    if not pending or pending["provider"] != provider or not secrets.compare_digest(pending["state"], request.GET.get("state", "")):
        return render(request, "pages/login.html", {"step": "email", "provider_error": True, "providers": oauth.enabled()}, status=400)
    try:
        user = oauth.exchange(provider, request.GET.dict(), request.build_absolute_uri(request.path), pending["verifier"], pending["state"])
    except oauth.OAuthError:
        return render(request, "pages/login.html", {"step": "email", "provider_error": True, "providers": oauth.enabled()}, status=502)
    account = _sign_in(request, user.email, user.provider, user.subject, trust_email=user.email_verified)
    return remember_owner(request, redirect(pending["next"]), account)


def telegram_login(request: HttpRequest) -> HttpResponse:
    if "telegram" not in oauth.enabled():
        raise Http404
    params = {k: v for k, v in request.GET.items() if k not in {"next"}}
    try:
        user = oauth.telegram_user(params)
    except (oauth.OAuthError, KeyError, ValueError):
        return render(request, "pages/login.html", {"step": "email", "provider_error": True, "providers": oauth.enabled()}, status=400)
    account = _sign_in(request, None, user.provider, user.subject)
    return remember_owner(request, redirect(_next_url(request)), account)


def telegram_link(request: HttpRequest) -> HttpResponse:
    """Open the bot with a one-time code; the bot's /start <code> ties this chat to the account."""
    owner = get_owner(request)
    if not owner or not owner.is_account or not settings.TELEGRAM_BOT_NAME:
        raise Http404
    code = secrets.token_urlsafe(16)
    cache.set(f"tg-link:{code}", str(owner.id), 3600)
    return redirect(f"https://t.me/{settings.TELEGRAM_BOT_NAME}?start={code}")


@require_POST
def telegram_unlink(request: HttpRequest) -> HttpResponse:
    if owner := get_owner(request):
        owner.telegram_chat_id = None
        owner.save(update_fields=["telegram_chat_id"])
    return redirect("account")


@csrf_exempt
@require_POST
def telegram_webhook(request: HttpRequest, secret: str) -> HttpResponse:
    """Bot updates. Only /start <code> matters: it links the chat to the account that asked for the code."""
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or not (secrets.compare_digest(secret, expected) and secrets.compare_digest(header, expected)):
        raise Http404
    try:
        message = json.loads(request.body).get("message") or {}
    except ValueError:
        return HttpResponse(status=200)
    chat_id, text = (message.get("chat") or {}).get("id"), message.get("text") or ""
    if chat_id and text.startswith("/start "):
        owner_id = cache.get(f"tg-link:{text.split(maxsplit=1)[1].strip()}")
        owner = Owner.objects.filter(id=owner_id).first() if owner_id else None
        if owner:
            owner.telegram_chat_id = chat_id
            owner.save(update_fields=["telegram_chat_id"])
            send_message(chat_id, "Готово: уведомления Duoverse подключены. Напишем, когда партнёр ответит на вопрос дня.")
        else:
            send_message(chat_id, "Ссылка устарела. Нажмите «Подключить Telegram» в разделе «Профиль» ещё раз.")
    return HttpResponse(status=200)


# ── payments (ADR-0011) ───────────────────────────────────────────────────
CHECKOUT = {"deep": "PRICE_DEEP", "plus": "PRICE_PLUS", "plus365": "PRICE_PLUS_YEAR", "gift": "PRICE_DEEP"}  # kind → price setting


@require_POST
def checkout(request: HttpRequest, kind: str) -> HttpResponse:
    owner = get_owner(request)
    if kind not in CHECKOUT:
        raise Http404
    if not owner or not owner.is_account:
        return _to_login(request, "save")
    pair = None
    if kind == "deep":
        try:
            pair = pairs_of(owner).filter(id=uuid.UUID(request.POST.get("pair", ""))).first()
        except ValueError:
            pair = None
    if kind == "deep" and not pair:
        raise Http404
    amount = getattr(settings, CHECKOUT[kind])
    purchase = Purchase.objects.create(owner=owner, pair=pair, kind=kind, amount=amount)
    description = f"Duoverse: {purchase.title}"
    return_url = request.build_absolute_uri(reverse("pay_return", args=[purchase.id]))
    if yookassa.enabled():
        if not owner.email:
            return _to_login(request, "save")  # a receipt needs an email
        try:
            pid, url = yookassa.create_payment(str(purchase.id), amount, description, str(owner.email), return_url)
        except yookassa.PaymentError:
            purchase.delete()
            return render(request, "pages/pay_result.html", {"ok": False, "retry": True}, status=502)
        purchase.provider_id = pid
        purchase.save(update_fields=["provider_id"])
        return redirect(url)
    if settings.DEBUG:  # no shop keys: a test checkout so the flow can be tried end to end
        return redirect("dev_checkout", pid=purchase.id)
    purchase.delete()
    return render(request, "pages/pay_result.html", {"ok": False, "unavailable": True}, status=503)


def _settle(purchase: Purchase) -> None:
    """Ask YooKassa for the real status; notifications and return visits only tell us *when* to ask."""
    if purchase.status != Purchase.Status.PENDING or not purchase.provider_id or not yookassa.enabled():
        return
    try:
        status = yookassa.payment_status(purchase.provider_id)
    except yookassa.PaymentError:
        return
    if status == "succeeded":
        mark_paid(purchase)
    elif status == "canceled":
        purchase.status = Purchase.Status.CANCELED
        purchase.save(update_fields=["status"])


def pay_return(request: HttpRequest, pid) -> HttpResponse:
    owner = get_owner(request)
    purchase = Purchase.objects.filter(id=pid, owner=owner).first() if owner else None
    if not purchase:
        raise Http404
    _settle(purchase)
    stored = latest_ready(purchase.pair) if purchase.pair and purchase.kind != "gift" else None
    back = reverse("stored_report", args=[stored.id]) + "razbor/" if stored else reverse("history")
    if purchase.kind == "plus":  # the month opens the daily extras, not the reports
        back = reverse("pair_invite")
    ctx = {"ok": purchase.status == "succeeded", "pending": purchase.status == "pending", "purchase": purchase, "back": back}
    if purchase.kind == "gift" and purchase.gift_code:
        ctx["gift_url"] = request.build_absolute_uri(reverse("gift", args=[purchase.gift_code]))
    return render(request, "pages/pay_result.html", ctx)


def gift(request: HttpRequest, code: str) -> HttpResponse:
    """A gifted full report: sign in, pick the pair it opens (or make one first — the code waits in the session)."""
    present = open_gift(code)
    if not present:
        return render(request, "pages/gift.html", {"state": "gone"}, status=404)
    owner = get_owner(request)
    if not owner or not owner.is_account:
        query = urlencode({"sheet": "1", "why": "gift", "next": request.path})
        return render(request, "pages/gift.html", {"state": "signin", "login_query": query})
    request.session["gift_code"] = present.gift_code
    locked = [p for p in pairs_of(owner).select_related("a", "b").order_by("-created_at") if not unlocked(p)]
    if request.method == "POST":
        pair = next((p for p in locked if str(p.id) == request.POST.get("pair")), None)
        if pair:
            redeem_gift(present, pair, owner)
            request.session.pop("gift_code", None)
            stored = latest_ready(pair)
            return redirect(reverse("stored_report", args=[stored.id]) + "razbor/" if stored else reverse("history"))
    return render(request, "pages/gift.html", {"state": "pick", "pairs": locked, "code": present.gift_code})


@csrf_exempt
@require_POST
def yookassa_webhook(request: HttpRequest) -> HttpResponse:
    try:
        payment_id = json.loads(request.body)["object"]["id"]
    except (ValueError, KeyError, TypeError):
        return HttpResponse(status=400)
    purchase = Purchase.objects.filter(provider_id=payment_id).first()
    if purchase:
        _settle(purchase)
    return HttpResponse(status=200)  # unknown ids are acknowledged so YooKassa stops retrying


def dev_checkout(request: HttpRequest, pid) -> HttpResponse:
    """DEBUG-only stand-in for the YooKassa page."""
    if not settings.DEBUG or yookassa.enabled():
        raise Http404
    owner = get_owner(request)
    purchase = Purchase.objects.filter(id=pid, owner=owner).first() if owner else None
    if not purchase:
        raise Http404
    if request.method == "POST":
        if request.POST.get("result") == "ok":
            mark_paid(purchase)
        else:
            purchase.status = Purchase.Status.CANCELED
            purchase.save(update_fields=["status"])
        return redirect("pay_return", pid=purchase.id)
    return render(request, "pages/dev_checkout.html", {"purchase": purchase})


@require_POST
def logout(request: HttpRequest) -> HttpResponse:
    return forget_device(request, redirect("landing"))


@require_POST
def device_revoke(request: HttpRequest, did) -> HttpResponse:
    device = get_device(request)
    if not device:
        raise Http404
    if str(did) == str(device.id):
        return forget_device(request, redirect("landing"))
    Device.objects.filter(owner=device.owner, id=did).delete()
    return redirect("account")


@require_POST
def logout_others(request: HttpRequest) -> HttpResponse:
    if device := get_device(request):
        Device.objects.filter(owner=device.owner).exclude(id=device.id).delete()
    return redirect("account")


# ── history, profiles, data ownership ─────────────────────────────────────
def history(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    items = []
    for pair in pairs_of(owner).select_related("a", "b", "owner", "partner") if owner else []:
        stored = latest_ready(pair)
        if stored:
            r = report_of(stored)
            items.append(
                {
                    "id": stored.id,
                    "names": f"{pair.a.name} и {pair.b.name}",
                    "created_at": stored.created_at,
                    "total_score": r.total_score,
                    "pair_type": r.pair_type.name,
                    "mode": dict(quick="Быстрый", extended="Расширенный", deep="Глубокий").get(pair.mode, pair.mode),
                    "pair_id": pair.id,
                    "b_id": pair.b_id,
                    "shared": pair.partner_id is not None,
                    "mine": pair.owner_id == owner.id,  # type: ignore[union-attr]
                }
            )
    return render(request, "pages/history.html", {"items": items})


@require_POST
def delete_report(request: HttpRequest, rid) -> HttpResponse:
    stored = _owned_report(request, rid)
    if stored.pair.owner_id != get_owner(request).id:  # type: ignore[union-attr]
        raise Http404  # a partner can leave the pair, not delete it
    stored.pair.reports.all().delete()
    return HttpResponse(status=204)


def profiles(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    people = [person_input(p) for p in owner.people.all()] if owner else []
    return render(request, "pages/profiles.html", {"profiles": people})


def _editable_person(request: HttpRequest, pid) -> tuple[Person, bool]:
    """A person this device may edit: its own profiles, or — for a joined partner — their own side of the pair."""
    owner = get_owner(request)
    if not owner:
        raise Http404
    person = Person.objects.filter(id=pid, owner=owner).first()
    if person:
        return person, False
    pair = Pair.objects.select_related("b").filter(partner=owner, b_id=pid).first()
    if not pair:
        raise Http404
    return pair.b, True


def profile_edit(request: HttpRequest, pid) -> HttpResponse:
    person, as_partner = _editable_person(request, pid)
    back = "history" if as_partner else "profiles"
    if request.method == "POST":
        if request.POST.get("action") == "delete" and not as_partner:
            Pair.objects.filter(models.Q(a=person) | models.Q(b=person)).delete()
            person.delete()
            return redirect("profiles")
        day = _parse_date(request.POST.get("date"))
        if day:
            person.name = request.POST.get("name", person.name).strip()[:80] or person.name
            person.gender = g if (g := request.POST.get("gender", "")) in ("f", "m") else ""
            person.birth = birth_payload(day, _parse_time(request.POST.get("time")), *_place_from(request, ""))
            person.save()
            for pair in Pair.objects.filter(models.Q(a=person) | models.Q(b=person)):
                request_report(pair)
        return redirect(back)
    return render(request, "pages/profile_edit.html", {"p": person_input(person), "cities": CITIES, "as_partner": as_partner, "back": back})


def account(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    device = get_device(request)
    email = str(owner.email) if owner and owner.is_account and owner.email else ""
    ctx = {
        "stats": {
            "reports": StoredReport.objects.filter(pair__in=pairs_of(owner), status="ready").count() if owner else 0,
            "people": owner.people.count() if owner else 0,
        },
        "email": email,
        "masked_email": (email[:2] + "•••" + email[email.index("@") :]) if "@" in (email or "") else "",
        "devices": owner.devices.all() if owner and owner.is_account else [],
        "telegram_bot": settings.TELEGRAM_BOT_NAME,
        "telegram_linked": bool(owner and owner.telegram_chat_id),
        "plus_until": plus_until(owner) if owner else None,
        "price_plus_year": settings.PRICE_PLUS_YEAR,
        "price_plus": settings.PRICE_PLUS,
        "privacy_email": settings.PRIVACY_EMAIL,
        "login_query": urlencode({"sheet": "1", "why": "profile", "next": reverse("account")}),
        "this_device": device.id if device else None,
        "avatars": [(k, v[0]) for k, v in AVATARS.items()],
        "pairs": [
            _cabinet_pair(request, p) for p in pairs_of(owner).select_related("a", "b", "owner", "partner").order_by("-created_at")[:6]
        ]
        if owner
        else [],
    }
    return render(request, "pages/account.html", ctx)


def _cabinet_pair(request: HttpRequest, pair: Pair) -> dict:
    stored = latest_ready(pair)
    url = reverse("stored_report", args=[stored.id]) if stored else ""
    return {
        "a": pair.a,
        "b": pair.b,
        "url": url,
        "story": reverse("pair_story", args=[pair.id]) if stored else "",
        **_pair_people(request, pair),
    }


def export_data(request: HttpRequest) -> HttpResponse:
    """GDPR/152-ФЗ: everything we keep for this account, decrypted, as one JSON file."""
    owner = get_owner(request)
    if not owner:
        raise Http404
    data = {
        "email": owner.email if owner.is_account else None,
        "people": [{"id": str(p.id), "name": p.name, "birth": p.birth, "answers": p.answers} for p in owner.people.all()],
        "reports": [s.snapshot for s in StoredReport.objects.filter(pair__in=pairs_of(owner), status="ready")],
        "plans": [{"pair": str(p.id), **p.plan} for p in pairs_of(owner) if p.plan],
        "intimacy": [{"pair": str(p.id), "mine": r.picks} for p in pairs_of(owner) for r in p.intimacy.filter(side=side_of(owner, p))],
        "dates": [{"pair": str(p.id), "entries": p.dates} for p in pairs_of(owner) if p.dates],
        # as you see it on the page: your own ideas never say whether they were reserved
        "wishes": [{"pair": str(p.id), **pair_wishes.view(p.wishes, side_of(owner, p))} for p in pairs_of(owner) if p.wishes],
        "notes": [{"pair": str(p.id), "notes": p.notes} for p in pairs_of(owner) if p.notes],
    }
    resp = HttpResponse(json.dumps(data, ensure_ascii=False, indent=2, default=str), content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="duoverse-data.json"'
    return resp


@require_POST
def delete_everything(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    if owner:
        owner.delete()  # cascades to devices, people, answers, own pairs and reports; joined pairs just lose this partner
    resp = redirect("landing")
    resp.delete_cookie(settings.OWNER_COOKIE)
    return resp


def not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return render(request, "errors/404.html", status=404)


def server_error(request: HttpRequest) -> HttpResponse:
    return render(request, "errors/500.html", status=500)


def manifest(request: HttpRequest) -> HttpResponse:
    """Web app manifest: lets people put Duoverse on the home screen like an app."""
    icon = lambda path, size, purpose="any": {"src": static(path), "sizes": size, "type": "image/png", "purpose": purpose}  # noqa: E731
    data = {
        "name": "Duoverse",
        "short_name": "Duoverse",
        "description": "Совместимость пары: разбор, вопрос дня и привычки на двоих",
        "lang": "ru",
        "start_url": "/daily/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#fbf7f2",
        "theme_color": "#fbf7f2",
        "icons": [
            icon("pwa/icon-192.png", "192x192"),
            icon("pwa/icon-512.png", "512x512"),
            icon("pwa/maskable-512.png", "512x512", "maskable"),
        ],
    }
    return HttpResponse(json.dumps(data, ensure_ascii=False), content_type="application/manifest+json")


SERVICE_WORKER = """
const CACHE = "duoverse-v1";
self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.add("/offline/")).then(() => self.skipWaiting())));
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;  // pages only: data stays live, static has its own caching
  e.respondWith(fetch(e.request).catch(() => caches.match("/offline/")));
});
"""


def service_worker(request: HttpRequest) -> HttpResponse:
    """Served from the site root so its scope covers every page; shows the offline page when there is no network."""
    resp = HttpResponse(SERVICE_WORKER, content_type="application/javascript")
    resp["Cache-Control"] = "no-cache"
    return resp


def healthz(request: HttpRequest) -> HttpResponse:
    from django.db import connection

    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001 — any DB failure means unhealthy
        return HttpResponse("db: down", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
