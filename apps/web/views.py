"""Thin views: read from the ReportProvider and render. No business logic here."""

import hashlib
import json
import secrets
import uuid
from datetime import date, time

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import models
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.compatibility import plan as habit_plan
from apps.compatibility.access import has_plus, mark_paid, plus_for_pair, unlocked
from apps.compatibility.domain.archetypes import DYNAMICS, ELEMENTS, MODES, ROLES, dynamic_for, pair_name
from apps.compatibility.domain.report import Report, ReportUnavailable
from apps.compatibility.infrastructure import oauth, yookassa
from apps.compatibility.infrastructure.telegram import send_message
from apps.compatibility.models import DailyAnswer, Device, Owner, Pair, Person, Purchase, QuizAnswer, StoredReport
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
)
from apps.core.domain.names import gen
from apps.psychology.domain import scoring as psy
from apps.psychology.domain.instruments import ITEMS, LIKERT, SECTIONS
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
    ("Big Five", "10 утверждений о характере", "user-round"),
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

PLANS = [
    {
        "name": "Бесплатно",
        "note": "Чтобы познакомиться",
        "price": "0 ₽",
        "per": "навсегда",
        "free": True,
        "cta": "Начать",
        "small": "без карты · вход по почте за минуту",
        "features": ["Итог: тип пары, балл и точность", "Приглашение партнёра", "Вопрос дня на двоих", "План привычек на неделю"],
    },
    {
        "name": "Глубокий разбор",
        "note": "Всё про одну пару",
        "price": "490 ₽",
        "per": "разово",
        "featured": True,
        "cta": "Выбрать разбор",
        "small": "разово за пару · открывается вам обоим · чек на почту",
        "features": [
            "Все 4 вселенные и индекс согласия",
            "Научный слой: Big Five, привязанность, Готтман",
            "«Почему так» у каждого вывода",
            "Открывается вам обоим",
            "План микропривычек",
            "PDF-версия",
        ],
    },
    {
        "name": "Пара+",
        "note": "Для тех, кто хочет каждый день",
        "price": "249 ₽",
        "per": "в месяц",
        "cta": "Подключить",
        "kind": "plus",
        "small": "на 30 дней · без автосписаний",
        "features": [
            "Полные разборы всех ваших пар",
            "Квизы для пары каждую неделю",
            "История ответов на вопросы дня",
            "Действует и для партнёра",
        ],
    },
]
COMPARE = [
    ("Балл пары и категории", (True, True, True)),
    ("Четыре вселенные", ("2 из 4", True, True)),
    ("Научный слой", (False, True, True)),
    ("«Почему так»", ("частично", True, True)),
    ("Партнёр по приглашению", (True, True, True)),
    ("PDF", (False, True, True)),
    ("Вопрос дня на двоих", (True, True, True)),
    ("Квизы и история ответов", (False, False, True)),
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


def page(request: HttpRequest, name: str) -> HttpResponse:
    return render(request, PAGES[name])


def set_scenario(request: HttpRequest, key: str) -> HttpResponse:
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
                reverse("wizard") + "?mode=extended",
            ),
            (d.get("time_place_b", False), f"Время и место · {b.name}", "наложения домов, композит", reverse("wizard") + "?mode=extended"),
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


def _plan_ctx(request: HttpRequest, stored: StoredReport | None) -> dict:
    raw = stored.pair.plan if stored else request.session.get("plan", {})
    return {**habit_plan.state(raw, timezone.localdate()), "rid": str(stored.id) if stored else "", "max": habit_plan.MAX_PICK}


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
    return JsonResponse(habit_plan.state(plan, timezone.localdate()))


@require_POST
def plan_pick(request: HttpRequest) -> HttpResponse:
    plan, allowed, pair = _plan_target(request)
    return _plan_save(request, habit_plan.pick(plan, request.POST.getlist("habit"), allowed, timezone.localdate()), pair)


@require_POST
def plan_done(request: HttpRequest) -> HttpResponse:
    plan, _, pair = _plan_target(request)
    return _plan_save(request, habit_plan.toggle(plan, request.POST.get("habit", ""), timezone.localdate()), pair)


def _demo(request: HttpRequest, template: str, **ctx) -> HttpResponse:
    try:
        report = report_provider().get_report(_scenario(request))
    except ReportUnavailable:
        return render(request, "report/error.html", {"retry_url": reverse("generating")}, status=503)
    return _render_report(request, report, template, reverse("report"), **ctx)


def landing(request: HttpRequest) -> HttpResponse:
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
    return render(request, "pages/pricing.html", {"plans": PLANS, "compare": COMPARE})


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
    """A new question every day, leaning on the pair's weakest spheres; both partners get the same one."""
    from apps.knowledge.infrastructure.repository import KnowledgeRepository

    kb = KnowledgeRepository()
    order = [s.key for s in sorted(report.spheres, key=lambda s: s.score)]
    pools = {k: kb.series(f"QUESTION:{k}:") for k in order}
    order = [k for k in order if pools[k]]
    if not order:
        return report.daily.question
    n = (today - date(2026, 1, 1)).days + int(hashlib.sha256(seed.encode()).hexdigest()[:6], 16)
    weak = order[:4]
    sphere = weak[(n // 2) % len(weak)] if n % 2 == 0 else order[(n // 2) % len(order)]  # every other day a weak sphere
    pool = pools[sphere]
    return pool[(n // 7) % len(pool)]["question"]


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
            "me_name": pair.a.name if side == "a" else pair.b.name,
            "partner_name": pair.b.name if side == "a" else pair.a.name,
        }
        return _render_report(request, report, "pages/daily.html", reverse("stored_report", args=[stored.id]), extra)
    demo = report_provider().get_report(_scenario(request))
    return _render_report(request, demo, "pages/daily.html", reverse("report"), {"daily_question": question_of_day(demo, "demo", today)})


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
    ctx = {"quiz": quiz, "pair": pair, "plus": plus_for_pair(pair), "has_partner": bool(pair.partner_id), "price_plus": settings.PRICE_PLUS}
    if request.method == "POST" and ctx["plus"]:
        try:
            picks = [int(request.POST[f"q{i}"]) for i in range(len(quiz["items"]))]
        except (KeyError, ValueError):
            return render(request, "pages/quiz_week.html", {**ctx, "error": True}, status=422)
        if all(0 <= p < len(item["options"]) for p, item in zip(picks, quiz["items"], strict=True)):
            _, created = QuizAnswer.objects.update_or_create(pair=pair, side=side, quiz_key=quiz["key"], defaults={"picks": picks})
            if created:
                notify_partner(pair, side, "quiz")
        return redirect("quiz_week")
    rows = {r.side: r.picks for r in QuizAnswer.objects.filter(pair=pair, quiz_key=quiz["key"])}
    mine, theirs = rows.get(side), rows.get("b" if side == "a" else "a")
    if mine and theirs:
        results = [
            {"q": item["q"], "mine": item["options"][m], "theirs": item["options"][t], "same": m == t}
            for item, m, t in zip(quiz["items"], mine, theirs, strict=True)
        ]
        ctx |= {"results": results, "match": round(100 * sum(r["same"] for r in results) / len(results))}
    me, partner = (pair.a.name, pair.b.name) if side == "a" else (pair.b.name, pair.a.name)
    return render(
        request, "pages/quiz_week.html", {**ctx, "mine": mine, "partner_done": bool(theirs), "me_name": me, "partner_name": partner}
    )


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
    return render(request, "partials/quick_result.html", {"q": report_provider().quick_result(da, db)})


def _wizard_ctx() -> dict:
    return {"modes": WIZARD_MODES, "quizzes": WIZARD_QUIZZES, "cities": CITIES}


def wizard(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return render(request, "pages/wizard.html", {**_wizard_ctx(), "mode": request.GET.get("mode", "quick")})
    da, db = _parse_date(request.POST.get("a_date")), _parse_date(request.POST.get("b_date"))
    if not (da and db):
        return render(request, "pages/wizard.html", {**_wizard_ctx(), "error": True}, status=422)
    mode = request.POST.get("mode", "quick") if request.POST.get("mode") in {"quick", "extended", "deep"} else "quick"
    owner = get_owner(request) or Owner.objects.create()

    def person(prefix: str, day: date) -> dict:
        return {
            "name": request.POST.get(f"{prefix}_name", "").strip()[:80],
            "date": day,
            "time": _parse_time(request.POST.get(f"{prefix}_time")),
            "place": request.POST.get(f"{prefix}_place", "").strip()[:80] or None,
        }

    pair = create_pair(owner, person("a", da), person("b", db), mode)
    target = reverse("person_quiz", args=[pair.a.id]) if mode == "deep" else reverse("generating") + f"?r={request_report(pair).id}"
    if not owner.is_account:  # data first, then «where do we save it?» — the calculation already runs meanwhile
        target = reverse("login") + "?" + urlencode({"next": target, "why": "save"})
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
        if stored and stored.status == StoredReport.Status.PENDING:
            step = len(steps) - 1  # keep the last step spinning until the worker finishes
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
        "quiz_url": reverse("person_quiz", args=[pair.a_id]),
        "invite_url": reverse("invite", args=[stored.id]),
        "share_url": request.build_absolute_uri(reverse("public_share", args=[share_token(stored)])),
    }
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
def _quiz_ctx() -> dict:
    return {
        "sections": [{"title": s.title, "hint": s.hint, "items": [{"id": i.id, "text": i.text} for i in s.items]} for s in SECTIONS],
        "likert": LIKERT,
    }


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
    return render(request, "pages/quiz.html", {**_quiz_ctx(), "person": person, "submit_url": request.path})


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


def together(request: HttpRequest) -> HttpResponse:
    """«Вдвоём» tab: the invite for your latest pair, the shared report if you joined one, the demo otherwise."""
    owner = get_owner(request)
    pair = pairs_of(owner).order_by("-created_at").first() if owner else None
    if pair and pair.owner_id == owner.id and not pair.partner_id:  # type: ignore[union-attr]
        return redirect("invite_new", pair_id=pair.id)
    if pair and (stored := latest_ready(pair)):
        return redirect("stored_report", rid=stored.id)
    return render(request, "pages/pair_invite.html", {})


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
    if not owner or not owner.is_account:
        return render(
            request,
            "pages/join.html",
            {**ctx, "state": "login", "login_url": reverse("login") + "?" + urlencode({"next": request.path, "why": "join"})},
        )
    if pair.partner_id != owner.id:
        if request.method == "POST" and request.POST.get("action") == "accept":
            pair.partner = owner
            pair.save(update_fields=["partner"])
            notify_partner(pair, "b", "joined")
            return redirect("join", code=pair.invite_code)
        return render(request, "pages/join.html", {**ctx, "state": "accept"})
    if not pair.b.answers:  # the partner fills in their own questionnaire
        if request.method == "POST":
            if _save_answers(request, pair.b) is None:
                return HttpResponse("answers incomplete", status=422)
            return redirect(reverse("generating") + f"?r={request_report(pair).id}")
        return render(request, "pages/quiz.html", {**_quiz_ctx(), "person": pair.b, "submit_url": request.path, "joining": True})
    stored = latest_ready(pair)
    return redirect(reverse("stored_report", args=[stored.id]) if stored else reverse("generating") + f"?r={request_report(pair).id}")


@require_POST
def unlink_partner(request: HttpRequest, pair_id) -> HttpResponse:
    owner = get_owner(request)
    pair = pairs_of(owner).filter(id=pair_id).first() if owner else None
    if not pair:
        raise Http404
    pair.partner = None
    pair.save(update_fields=["partner"])
    invite_code(pair, fresh=True)
    return redirect("history")


# ── accounts: sign in by an emailed code, no passwords (ADR-0010) ─────────
def _next_url(request: HttpRequest) -> str:
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    return nxt if url_has_allowed_host_and_scheme(nxt, {request.get_host()}, require_https=request.is_secure()) else reverse("account")


LOGIN_WHY = {
    "save": "Почти готово. Куда сохранить ваш разбор? Пришлём код на почту: пароль не нужен, а разбор откроется с любого устройства.",
    "invite": "Чтобы пригласить партнёра, войдите по почте: так вы оба найдёте вашу пару с любого устройства.",
    "join": "Войдите по почте, чтобы присоединиться к паре. Пароль не нужен — пришлём код.",
}


def login(request: HttpRequest) -> HttpResponse:
    ctx = {
        "next": _next_url(request),
        "why": LOGIN_WHY.get(request.GET.get("why", ""), ""),
        "save": request.GET.get("why") == "save",
        "providers": oauth.enabled(),
        "telegram_bot": settings.TELEGRAM_BOT_NAME,
    }
    if request.method != "POST":
        return render(request, "pages/login.html", {**ctx, "step": "email"})
    email = request.POST.get("email", "").strip()
    try:
        validate_email(email)
    except ValidationError:
        return render(request, "pages/login.html", {**ctx, "step": "email", "email": email, "error": True}, status=422)
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
    return render(request, "pages/login.html", {**ctx, "step": "code", "email": email, "throttled": code is None})


@require_POST
def login_verify(request: HttpRequest) -> HttpResponse:
    h = request.session.get("login_hash", "")
    email = check_login_code(h, request.POST.get("code", "")) if h else None
    if not email:
        ctx = {"next": _next_url(request), "step": "code", "email": request.POST.get("email", ""), "error": True}
        return render(request, "pages/login.html", ctx, status=422)
    return _finish_login(request, email)


def login_link(request: HttpRequest, token: str) -> HttpResponse:
    parsed = from_login_link(token)
    email = check_login_code(*parsed) if parsed else None
    if not email:
        return render(request, "pages/login.html", {"next": _next_url(request), "step": "email", "expired": True}, status=410)
    return _finish_login(request, email)


def _finish_login(request: HttpRequest, email: str) -> HttpResponse:
    account = sign_in(get_owner(request), email)
    request.session.pop("login_hash", None)
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
    account = sign_in(get_owner(request), user.email, user.provider, user.subject, trust_email=user.email_verified)
    return remember_owner(request, redirect(pending["next"]), account)


def telegram_login(request: HttpRequest) -> HttpResponse:
    if "telegram" not in oauth.enabled():
        raise Http404
    params = {k: v for k, v in request.GET.items() if k not in {"next"}}
    try:
        user = oauth.telegram_user(params)
    except (oauth.OAuthError, KeyError, ValueError):
        return render(request, "pages/login.html", {"step": "email", "provider_error": True, "providers": oauth.enabled()}, status=400)
    account = sign_in(get_owner(request), None, user.provider, user.subject)
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
            send_message(chat_id, "Ссылка устарела. Нажмите «Подключить Telegram» в разделе «Мои данные» ещё раз.")
    return HttpResponse(status=200)


# ── payments (ADR-0011) ───────────────────────────────────────────────────
@require_POST
def checkout(request: HttpRequest, kind: str) -> HttpResponse:
    owner = get_owner(request)
    if kind not in ("deep", "plus"):
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
    amount = settings.PRICE_DEEP if kind == "deep" else settings.PRICE_PLUS
    purchase = Purchase.objects.create(owner=owner, pair=pair, kind=kind, amount=amount)
    description = "Duoverse: полный разбор пары" if kind == "deep" else f"Duoverse: Пара+ на {settings.PLUS_DAYS} дней"
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
    stored = latest_ready(purchase.pair) if purchase.pair else None
    back = reverse("stored_report", args=[stored.id]) + "razbor/" if stored else reverse("history")
    return render(
        request,
        "pages/pay_result.html",
        {"ok": purchase.status == "succeeded", "pending": purchase.status == "pending", "purchase": purchase, "back": back},
    )


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
            person.birth = birth_payload(day, _parse_time(request.POST.get("time")), request.POST.get("place", "").strip() or None)
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
        "plus_until": Purchase.objects.filter(owner=owner, kind="plus", status="succeeded")
        .order_by("-valid_until")
        .values_list("valid_until", flat=True)
        .first()
        if has_plus(owner)
        else None,
        "price_plus": settings.PRICE_PLUS,
        "this_device": device.id if device else None,
    }
    return render(request, "pages/account.html", ctx)


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
