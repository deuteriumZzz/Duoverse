from django.conf import settings

from config.container import report_provider


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
        "history": {"history", "profiles", "profile_edit", "account"},
    }
    tabbar = [
        (name, ic, label, nav in groups[name])
        for name, ic, label in [
            ("landing", "house", "Главная"),
            ("report", "chart-pie", "Отчёт"),
            ("daily", "sun", "Сегодня"),
            ("pair_invite", "users", "Вдвоём"),
            ("history", "archive", "Мои"),
        ]
    ]
    return {
        "tabbar": tabbar,
        "debug": settings.DEBUG,
        "dev": settings.DEBUG and request.session.get("dev", False),
        "scenarios": report_provider().scenarios(),
        "scenario": request.session.get("scenario", "ideal"),
        "nav": request.resolver_match.url_name if request.resolver_match else "",
    }
