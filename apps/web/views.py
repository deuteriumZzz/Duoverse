"""Thin views: read from the ReportProvider and render. No business logic here."""

import json
from datetime import date, time

from django.core.mail import send_mail
from django.db import models
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.compatibility import plan as habit_plan
from apps.compatibility.domain.archetypes import DYNAMICS, ELEMENTS, MODES, ROLES, dynamic_for, pair_name
from apps.compatibility.domain.report import Report, ReportUnavailable
from apps.compatibility.models import Owner, Pair, Person, StoredReport
from apps.compatibility.services import (
    birth_payload,
    create_pair,
    forget_owner,
    from_invite_token,
    from_magic_token,
    from_share_token,
    get_owner,
    invite_token,
    latest_ready,
    magic_token,
    person_input,
    remember_owner,
    report_of,
    request_report,
    share_token,
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
        "small": "без карты и регистрации",
        "features": ["Быстрый отчёт по датам", "Балл пары и 3 категории", "Арканы партнёров и пары", "Вопрос дня"],
    },
    {
        "name": "Глубокий разбор",
        "note": "Всё про одну пару",
        "price": "490 ₽",
        "per": "разово",
        "featured": True,
        "cta": "Открыть разбор",
        "small": "без регистрации · чек придёт на email",
        "features": [
            "Все 4 вселенные и индекс согласия",
            "Научный слой: Big Five, привязанность, Готтман",
            "«Почему так» у каждого вывода",
            "Парный режим",
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
        "small": "отмена в один клик · без аккаунта",
        "features": ["Всё из глубокого разбора", "Безлимитные пересчёты", "Ежедневный слой без ограничений", "История и сравнение отчётов"],
    },
]
COMPARE = [
    ("Балл пары и категории", (True, True, True)),
    ("Четыре вселенные", ("2 из 4", True, True)),
    ("Научный слой", (False, True, True)),
    ("«Почему так»", ("частично", True, True)),
    ("Парный режим", (False, True, True)),
    ("PDF", (False, True, True)),
    ("Вопрос дня", ("1 в день", "1 в день", "без лимита")),
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


def daily(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    pair = owner.pairs.first() if owner else None
    stored = latest_ready(pair) if pair else None
    if stored:
        return _render_report(
            request, report_of(stored), "pages/daily.html", reverse("stored_report", args=[stored.id]), {"stored": stored}
        )
    return _demo(request, "pages/daily.html")


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
    if mode == "deep":
        resp = redirect(reverse("person_quiz", args=[pair.a.id]))
    else:
        resp = redirect(reverse("generating") + f"?r={request_report(pair).id}")
    return remember_owner(resp, owner)


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
    if not stored or not owner or stored.pair.owner_id != owner.id:
        raise Http404
    return stored


def _stored(request: HttpRequest, rid, template: str, **ctx) -> HttpResponse:
    stored = _owned_report(request, rid)
    if stored.status == StoredReport.Status.PENDING:
        return redirect(reverse("generating") + f"?r={stored.id}")
    if stored.status == StoredReport.Status.FAILED:
        return render(request, "report/error.html", {"retry_url": reverse("retry_report", args=[stored.id])}, status=503)
    pair = stored.pair
    extra = {
        "stored": stored,
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
    owner = get_owner(request)
    person = Person.objects.filter(id=pid, owner=owner).first() if owner else None
    if not person:
        raise Http404
    if request.method == "POST":
        if _save_answers(request, person) is None:
            return HttpResponse("answers incomplete", status=422)
        pair = Pair.objects.filter(owner=owner).filter(models.Q(a=person) | models.Q(b=person)).first()
        if pair is None:
            return redirect("history")
        if pair.mode == "deep" and person == pair.a and not pair.b.answers:
            return redirect(reverse("invite_new", args=[pair.id]))
        return redirect(reverse("generating") + f"?r={request_report(pair).id}")
    return render(request, "pages/quiz.html", {**_quiz_ctx(), "person": person, "submit_url": request.path})


# ── pair mode: partner answers by signed link ─────────────────────────────
def invite(request: HttpRequest, rid) -> HttpResponse:
    stored = _owned_report(request, rid)
    return _invite_page(request, stored.pair)


def invite_new(request: HttpRequest, pair_id) -> HttpResponse:
    owner = get_owner(request)
    pair = Pair.objects.filter(id=pair_id, owner=owner).first() if owner else None
    if not pair:
        raise Http404
    return _invite_page(request, pair)


def _invite_page(request: HttpRequest, pair: Pair) -> HttpResponse:
    link = request.build_absolute_uri(reverse("join", args=[invite_token(pair.b)]))
    return render(
        request, "pages/pair_invite.html", {"invite_link": link, "partner": pair.b, "waiting_url": reverse("pair_status", args=[pair.id])}
    )


def pair_status(request: HttpRequest, pair_id) -> HttpResponse:
    owner = get_owner(request)
    pair = Pair.objects.filter(id=pair_id, owner=owner).first() if owner else None
    if not pair:
        raise Http404
    if pair.b.answers:
        return redirect(reverse("generating") + f"?r={request_report(pair).id}")
    return render(request, "pages/pair_waiting.html", {"partner": pair.b, "pair": pair})


def join(request: HttpRequest, token: str) -> HttpResponse:
    person = from_invite_token(token)
    if not person:
        raise Http404
    if request.method == "POST":
        if _save_answers(request, person) is None:
            return HttpResponse("answers incomplete", status=422)
        return render(request, "pages/join_done.html", {"person": person})
    return render(request, "pages/quiz.html", {**_quiz_ctx(), "person": person, "submit_url": request.path, "joining": True})


# ── history, profiles, data ownership ─────────────────────────────────────
def history(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    items = []
    for pair in owner.pairs.select_related("a", "b") if owner else []:
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
                }
            )
    return render(request, "pages/history.html", {"items": items})


@require_POST
def delete_report(request: HttpRequest, rid) -> HttpResponse:
    _owned_report(request, rid).pair.reports.all().delete()
    return HttpResponse(status=204)


def profiles(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    people = [person_input(p) for p in owner.people.all()] if owner else []
    return render(request, "pages/profiles.html", {"profiles": people})


def profile_edit(request: HttpRequest, pid) -> HttpResponse:
    owner = get_owner(request)
    person = Person.objects.filter(id=pid, owner=owner).first() if owner else None
    if not person:
        raise Http404
    if request.method == "POST":
        if request.POST.get("action") == "delete":
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
        return redirect("profiles")
    return render(request, "pages/profile_edit.html", {"p": person_input(person), "cities": CITIES})


def account(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    stats = {
        "reports": StoredReport.objects.filter(pair__owner=owner, status="ready").count() if owner else 0,
        "people": owner.people.count() if owner else 0,
    }
    return render(request, "pages/account.html", {"stats": stats})


def export_data(request: HttpRequest) -> HttpResponse:
    """GDPR/152-ФЗ: everything we keep for this device, decrypted, as one JSON file."""
    owner = get_owner(request)
    if not owner:
        raise Http404
    data = {
        "people": [{"id": str(p.id), "name": p.name, "birth": p.birth, "answers": p.answers} for p in owner.people.all()],
        "reports": [s.snapshot for s in StoredReport.objects.filter(pair__owner=owner, status="ready")],
    }
    resp = HttpResponse(json.dumps(data, ensure_ascii=False, indent=2, default=str), content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="duoverse-data.json"'
    return resp


@require_POST
def send_magic_link(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    email = request.POST.get("email", "").strip()
    if not owner or "@" not in email:
        return HttpResponse("Нет данных для переноса или неверный email", status=422)
    owner.email = email
    owner.save(update_fields=["email"])
    link = request.build_absolute_uri(reverse("magic", args=[magic_token(owner)]))
    send_mail(
        "Ваши разборы Duoverse",
        f"Откройте ссылку на новом устройстве, чтобы увидеть свои разборы (действует сутки):\n{link}",
        None,
        [email],
    )
    return HttpResponse(status=204)


def magic(request: HttpRequest, token: str) -> HttpResponse:
    owner = from_magic_token(token)
    if not owner:
        raise Http404
    return remember_owner(redirect("history"), owner)


@require_POST
def delete_everything(request: HttpRequest) -> HttpResponse:
    owner = get_owner(request)
    if owner:
        owner.delete()  # cascades to people, answers, pairs, reports
    return forget_owner(redirect("landing"))


def not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return render(request, "errors/404.html", status=404)


def server_error(request: HttpRequest) -> HttpResponse:
    return render(request, "errors/500.html", status=500)


def healthz(request: HttpRequest) -> HttpResponse:
    from django.db import connection

    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001 — any DB failure means unhealthy
        return HttpResponse("db: down", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
