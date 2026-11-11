from django.conf import settings
from django.utils.functional import SimpleLazyObject

from config.container import report_provider


def _me(request) -> dict | None:
    """Who is looking, for the header avatar menu; computed only when a template asks for it."""
    from apps.compatibility.access import has_plus
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
        "plus": has_plus(owner),
    }


def prototype(request):
    # Dev tools (scenario switcher, simulated partner answers) stay hidden unless ?dev=1 — the product must not look like a demo.
    if settings.DEBUG and request.GET.get("dev") in {"0", "1"}:
        request.session["dev"] = request.GET["dev"] == "1"
    nav = request.resolver_match.url_name if request.resolver_match else ""
    groups = {
        "landing": {"landing", "start", "wizard"},
        "report": {"report", "report_tab", "share", "weights", "generating"},
        "daily": {"daily"},
        "pair_invite": {"pair_invite", "pair_waiting", "pair_ready"},
        "account": {"history", "profiles", "profile_edit", "account"},
    }
    tabbar = [
        (name, ic, label, nav in groups[name])
        for name, ic, label in [
            ("landing", "house", "Главная"),
            ("report", "chart-pie", "Отчёт"),
            ("daily", "sun", "Сегодня"),
            ("pair_invite", "users", "Вдвоём"),
            ("account", "circle-user-round", "Профиль"),
        ]
    ]
    return {
        "tabbar": tabbar,
        "me": SimpleLazyObject(lambda: _me(request)),
        "debug": settings.DEBUG,
        "dev_screens": settings.DEV_SCREENS,
        "dev": settings.DEBUG and request.session.get("dev", False),
        "scenarios": report_provider().scenarios(),
        "scenario": request.session.get("scenario", "ideal"),
        "nav": request.resolver_match.url_name if request.resolver_match else "",
    }
