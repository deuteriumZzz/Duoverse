from django.conf import settings
from django.utils.functional import SimpleLazyObject

from config.container import report_provider


def _me(request) -> dict | None:
    """Who is looking, for the header avatar menu; computed only when a template asks for it."""
    from apps.compatibility.access import shared_plus_until
    from apps.compatibility.services import get_owner
    from apps.web.avatars import DEFAULT

    owner = get_owner(request)
    if not owner:
        return None
    first = owner.pairs.select_related("a").order_by("-created_at").first()
    return {
        "avatar": owner.avatar or DEFAULT,
        "name": owner.name or (first.a.name if first else ""),
        "account": owner.is_account,
        "plus_until": (until := shared_plus_until(owner)),
        "plus": bool(until),  # «Пара+» of either partner — the same rule that opens the features
    }


def prototype(request):
    # Dev tools (scenario switcher, simulated partner answers) stay hidden unless ?dev=1 — the product must not look like a demo.
    if settings.DEBUG and request.GET.get("dev") in {"0", "1"}:
        request.session["dev"] = request.GET["dev"] == "1"
    nav = request.resolver_match.url_name if request.resolver_match else ""
    groups = {
        "landing": {"landing", "start", "wizard"},
        "report": {"report", "report_tab", "share", "weights", "generating", "stored_report", "stored_tab"},
        "daily": {"daily", "quiz_week"},
        "pair_invite": {"pair_invite", "pair_waiting", "pair_ready", "pair_calendar", "wish_map", "intimacy", "pair_story", "library"},
        "account": {"history", "profiles", "profile_edit", "account"},
    }

    def tabs() -> list:
        """Four tabs for everyone, one job each: «Главная» your home, «Сегодня» what to do now, «Отчёт» who you are
        together, «Профиль» you. Home depends on who looks: a guest gets the page about Duoverse (its «вдвоём» section shows
        what a couple gets), a couple gets their pair — the tree, the path, what's yours. «Отчёт» is your own latest report
        once there is one (made without an account too), the sample only before that."""
        from django.urls import reverse

        from apps.compatibility.services import get_owner, latest_ready, pairs_of

        owner = get_owner(request)
        pair = pairs_of(owner).order_by("-created_at").first() if owner else None
        stored = latest_ready(pair) if pair else None
        items = [
            ("landing", "house", "Главная", reverse("landing")),
            ("daily", "sun", "Сегодня", reverse("daily")),
            ("report", "chart-pie", "Отчёт", reverse("stored_report", args=[stored.id]) if stored else reverse("report")),
            ("account", "circle-user-round", "Профиль", reverse("account")),
        ]
        if owner and owner.is_account and pair:
            items[0] = ("pair_invite", "house", "Главная", reverse("pair_invite"))
        return [(name, ic, label, nav in groups[name], href) for name, ic, label, href in items]

    return {
        # «Пара+» the way people compare it: the year as a price per month, and how much it saves against paying monthly
        "plus_from": round(settings.PRICE_PLUS_YEAR / 12),
        "price_plus_year": settings.PRICE_PLUS_YEAR,
        "plus_save": round(100 - settings.PRICE_PLUS_YEAR * 100 / (settings.PRICE_PLUS * 12)),
        "tabbar": SimpleLazyObject(tabs),
        "me": SimpleLazyObject(lambda: _me(request)),
        "debug": settings.DEBUG,
        "dev_screens": settings.DEV_SCREENS,
        "dev": settings.DEBUG and request.session.get("dev", False),
        "scenarios": report_provider().scenarios(),
        "scenario": request.session.get("scenario", "ideal"),
        "nav": request.resolver_match.url_name if request.resolver_match else "",
    }
