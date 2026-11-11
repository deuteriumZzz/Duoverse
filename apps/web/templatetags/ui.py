"""Template helpers: icons, generated SVG (radar, arcana art), labels."""

import math
import secrets

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()

LABELS = {
    "low": "низкий",
    "mid": "средний",
    "high": "высокий",
    "synergy": "Синергия",
    "neutral": "Нейтрально",
    "attention": "Внимание",
    "risk": "Риск",
    "symbolic": "символический слой",
    "scientific": "научный слой",
}
TONE_ICONS = {"synergy": "check", "neutral": "minus", "attention": "eye", "risk": "triangle-exclamation-point"}
ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


@register.simple_tag
def asset(path: str) -> str:
    """Static URL versioned by mtime, so browsers drop cached CSS/JS/sprite after `npm run build`."""
    try:
        v = int((settings.BASE_DIR / "static" / path).stat().st_mtime)
    except OSError:
        v = 0
    return f"{static(path)}?v={v}"


def _sprite_url() -> str:
    return asset("icons/sprite.svg")


@register.simple_tag
def avatar(key: str | None, size: int = 40, cls: str = "") -> str:
    from apps.web.avatars import render

    return render(key, size, cls)


@register.simple_tag
def icon(name: str, cls: str = "size-5") -> str:
    return format_html(
        '<svg class="{} shrink-0" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><use href="{}#{}"/></svg>',
        cls,
        _sprite_url(),
        name,
    )


@register.filter
def label(value: str) -> str:
    return LABELS.get(value, value)


@register.filter
def get_item(mapping: dict, key: str):
    return mapping.get(key, "")


@register.filter
def tone_icon(tone: str) -> str:
    return TONE_ICONS.get(tone, "minus")


@register.filter
def roman(n: int) -> str:
    if n == 22:
        return "0"
    out = ""
    for v, s in ROMAN:
        while n >= v:
            out, n = out + s, n - v
    return out


@register.filter
def score_tone(score: int | None) -> str:
    if score is None:
        return "neutral"
    return "synergy" if score >= 75 else "neutral" if score >= 60 else "attention" if score >= 45 else "risk"


@register.filter
def signed(x: float) -> str:
    return f"+{x:.1f}" if x > 0 else f"−{abs(x):.1f}"


@register.simple_tag
def radar_svg(categories, size: int = 320) -> str:
    """Category radar. Shape grows from the centre once the parent gets `.in`."""
    c, r, n = size / 2, size / 2 - 58, len(categories)

    def pt(i: int, v: float) -> tuple[float, float]:
        a = -math.pi / 2 + 2 * math.pi * i / n
        return c + r * v * math.cos(a), c + r * v * math.sin(a)

    def poly(points) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)

    parts = [
        f'<svg viewBox="0 0 {size} {size}" class="w-full h-auto overflow-visible" role="img" aria-label="Радар совместимости по категориям">',
        '<defs><linearGradient id="radar-fill" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="var(--color-a)" stop-opacity=".55"/>'
        '<stop offset="1" stop-color="var(--color-b)" stop-opacity=".5"/></linearGradient></defs>',
    ]
    for lvl in (0.25, 0.5, 0.75, 1):
        parts.append(f'<polygon points="{poly(pt(i, lvl) for i in range(n))}" fill="none" stroke="var(--color-line)"/>')
    for i in range(n):
        x, y = pt(i, 1)
        parts.append(f'<line x1="{c}" y1="{c}" x2="{x:.1f}" y2="{y:.1f}" stroke="var(--color-line)"/>')
    pts = [pt(i, cat.score / 100) for i, cat in enumerate(categories)]
    parts.append(
        f'<g class="radar-shape"><polygon points="{poly(pts)}" fill="url(#radar-fill)"/>'
        f'<polygon class="radar-line" pathLength="1" points="{poly(pts)}" fill="none" stroke="var(--color-ink)" stroke-width="2.5" stroke-linejoin="round"/></g>'
    )
    for i, ((x, y), cat) in enumerate(zip(pts, categories, strict=False)):
        parts.append(
            f'<circle class="radar-dot" data-cat-dot="{escape(cat.key)}" style="--i:{i}" cx="{x:.1f}" cy="{y:.1f}" r="5" fill="var(--color-paper)" stroke="var(--color-ink)" stroke-width="2.5"/>'
        )
    for i, cat in enumerate(categories):
        x, y = pt(i, 1.24)
        anchor = "middle" if abs(x - c) < 10 else ("start" if x > c else "end")
        parts.append(
            f'<text x="{x:.1f}" y="{y - 4:.1f}" text-anchor="{anchor}" font-size="11.5" font-weight="700" fill="var(--color-ink-2)">'
            f'<tspan x="{x:.1f}">{escape(cat.title.split(" и ")[0])}</tspan>'
            f'<tspan x="{x:.1f}" dy="14" font-family="var(--font-mono)" fill="var(--color-ink-3)">{int(cat.score)}</tspan></text>'
        )
    parts.append("</svg>")
    return mark_safe("".join(parts))


@register.simple_tag
def arcana_art(number: int, side: str = "pair") -> str:
    """Original generative emblem for a major arcana — deterministic per number, no third-party art."""
    number = int(number)
    fill = {"a": "var(--color-a)", "b": "var(--color-b)"}.get(side, "var(--color-pair)")
    rays, rings, dots, tilt = 4 + number % 9, 1 + number % 3, 3 + number % 6, (number * 37) % 360

    def polar(radius: float, deg: float) -> tuple[str, str]:
        return f"{60 + radius * math.cos(math.radians(deg)):.1f}", f"{60 + radius * math.sin(math.radians(deg)):.1f}"

    parts = ['<svg viewBox="0 0 120 120" class="w-full h-full" aria-hidden="true">']
    for k in range(rings):
        dash = ' stroke-dasharray="3 4"' if k % 2 else ""
        parts.append(f'<circle cx="60" cy="60" r="{14 + 9 * k}" fill="none" stroke="var(--color-ink)" stroke-width="1.4"{dash}/>')
    for i in range(rays):
        x, y = polar(46, tilt + 360 * i / rays)
        parts.append(
            f'<line x1="60" y1="60" x2="{x}" y2="{y}" stroke="var(--color-ink)" stroke-width="1.6" stroke-linecap="round" opacity=".85"/>'
        )
    parts.append(
        f'<circle cx="60" cy="60" r="20" fill="{fill}" stroke="var(--color-ink)" stroke-width="1.6"/>'
        if number % 3 == 0
        else f'<rect x="44" y="44" width="32" height="32" rx="9" fill="{fill}" stroke="var(--color-ink)" stroke-width="1.6" transform="rotate(45 60 60)"/>'
        if number % 3 == 1
        else f'<path d="M60 38 L80 73 L40 73 Z" fill="{fill}" stroke="var(--color-ink)" stroke-width="1.6" stroke-linejoin="round"/>'
    )
    for i in range(dots):
        x, y = polar(52, -tilt + 360 * i / dots)
        parts.append(f'<circle cx="{x}" cy="{y}" r="3.2" fill="var(--color-ink)"/>')
    parts.append('<circle cx="60" cy="60" r="4" fill="var(--color-paper)" stroke="var(--color-ink)" stroke-width="1.6"/></svg>')
    return mark_safe("".join(parts))


ASPECT_KEYS = {"соединение": "conj", "секстиль": "sextile", "квадрат": "square", "трин": "trine", "оппозиция": "opp"}
GLYPHS = {"Солнце": "☉", "Луна": "☽", "Меркурий": "☿", "Венера": "♀", "Марс": "♂", "Юпитер": "♃", "Сатурн": "♄"}
TONE_STROKE = {
    "synergy": "var(--color-synergy)",
    "neutral": "var(--color-ink-3)",
    "attention": "var(--color-attention)",
    "risk": "var(--color-risk)",
}


@register.simple_tag
def synastry_svg(astro) -> str:
    """Two charts as constellations that spin into one wheel; aspect midpoints form the pair's constellation.

    Animation phases are CSS classes toggled on the parent (syn-1 → syn-3).
    """
    c, ra, rb = 200, 92, 150

    def xy(lon: float, r: float) -> tuple[float, float]:
        a = math.radians(180 - lon)  # 0° Aries on the left, counter-clockwise like a chart wheel
        return c + r * math.cos(a), c - r * math.sin(a)

    all_glyphs = {p.name: p.glyph for p in astro.planets_a + astro.planets_b}
    pa = {p.name: xy(p.lon, ra) for p in astro.planets_a}
    pb = {p.name: xy(p.lon, rb) for p in astro.planets_b}

    def figure(points: dict, cls: str, color: str, r: int) -> str:
        ordered = [points[p.name] for p in sorted(getattr(astro, f"planets_{cls}"), key=lambda p: p.lon)]
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in ordered + ordered[:1])
        out = [
            f'<g class="syn-fig syn-{cls}">',
            f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.2" stroke-opacity=".45" stroke-dasharray="3 4"/>',
        ]
        for name, (x, y) in points.items():
            lx, ly = xy([p.lon for p in getattr(astro, f"planets_{cls}") if p.name == name][0], r + (16 if cls == "b" else -17))
            out.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="var(--color-paper)" stroke-width="2"/>'
                f'<text class="syn-glyph" x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="middle" font-size="13" fill="{color}">{escape(all_glyphs.get(name) or GLYPHS.get(name, "•"))}</text>'
            )
        out.append("</g>")
        return "".join(out)

    parts = [
        f'<svg viewBox="0 0 {2 * c} {2 * c}" class="h-auto w-full overflow-visible" role="img" aria-label="Синастрия: аспекты между картами как созвездие">',
        f'<g class="syn-rings"><circle cx="{c}" cy="{c}" r="{rb}" fill="none" stroke="var(--color-line)" stroke-width="1.5"/>'
        f'<circle cx="{c}" cy="{c}" r="{ra}" fill="none" stroke="var(--color-line)" stroke-width="1.5" stroke-dasharray="2 5"/>',
    ]
    for k in range(12):
        x1, y1 = xy(k * 30, rb + 6)
        x2, y2 = xy(k * 30, rb + 14)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="var(--color-ink-3)" stroke-width="1.5"/>')
    parts.append("</g>")
    parts.append(figure(pa, "a", "var(--color-a)", ra))
    parts.append(figure(pb, "b", "var(--color-b)", rb))

    mids = []
    for asp in astro.aspects:
        if asp.planet_a not in pa or asp.planet_b not in pb:
            continue
        (x1, y1), (x2, y2) = pa[asp.planet_a], pb[asp.planet_b]
        mids.append(((x1 + x2) / 2, (y1 + y2) / 2))
        parts.append(
            f'<line class="syn-asp" data-hover-target="asp-{escape(asp.key)}" style="--i:{len(mids)}" pathLength="1" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{TONE_STROKE.get(asp.tone)}" stroke-width="2.5" stroke-linecap="round"/>'
        )

    if len(mids) > 2:
        ordered = sorted(mids, key=lambda m: math.atan2(m[1] - c, m[0] - c))
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in ordered + ordered[:1])
        parts.append(
            f'<g class="syn-pair"><polyline class="syn-pair-line" pathLength="1" points="{path}" fill="var(--color-pair)" fill-opacity=".18" stroke="var(--color-ink)" stroke-width="1.6" stroke-linejoin="round"/>'
        )
        for k, (x, y) in enumerate(ordered):
            parts.append(
                f'<path class="syn-star" style="--i:{k}" transform="translate({x:.1f} {y:.1f})" d="M0 -7 L1.8 -1.8 L7 0 L1.8 1.8 L0 7 L-1.8 1.8 L-7 0 L-1.8 -1.8 Z" fill="var(--color-ink)"/>'
            )
        parts.append("</g>")
    parts.append("</svg>")
    return mark_safe("".join(parts))


@register.simple_tag
def mark(cls: str = "h-7 w-10", merge: bool = False, light: bool = False) -> str:
    """Brand mark: two orbits whose shared lens holds the pair. Works in one colour; `merge` animates the meeting."""
    uid = secrets.token_hex(3)
    ink = "var(--color-milk)" if light else "var(--color-ink)"
    return mark_safe(
        f'<svg viewBox="0 0 40 28" class="mark {cls}{" merge" if merge else ""}" aria-hidden="true">'
        f'<defs><linearGradient id="mg{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="var(--color-a)"/><stop offset="1" stop-color="var(--color-b)"/></linearGradient>'
        f'<clipPath id="mc{uid}"><circle class="mark-a" cx="14" cy="14" r="10"/></clipPath></defs>'
        f'<g clip-path="url(#mc{uid})"><circle class="mark-b" cx="26" cy="14" r="10" fill="url(#mg{uid})"/></g>'
        f'<circle class="mark-a" cx="14" cy="14" r="10" fill="none" stroke="{ink}" stroke-width="1.7"/>'
        f'<circle class="mark-b" cx="26" cy="14" r="10" fill="none" stroke="{ink}" stroke-width="1.7"/>'
        f'<path class="mark-star" d="M20 0.6 21 3.6 24 4.6 21 5.6 20 8.6 19 5.6 16 4.6 19 3.6Z" fill="{ink}"/></svg>'
    )


SIGN_GLYPHS = "♈♉♊♋♌♍♎♏♐♑♒♓"


@register.simple_tag
def bi_wheel_svg(astro) -> str:
    """Bi-wheel: zodiac ring, partner A inside, partner B outside, A's houses, major aspects as chords."""
    c, r_zod_o, r_zod_i, r_b, r_a, r_core = 200, 192, 168, 146, 112, 82
    asc = astro.houses_a[0] if astro.houses_a else 0.0  # rotate so A's Ascendant sits on the left

    def xy(lon: float, r: float) -> tuple[float, float]:
        ang = math.radians(180 - (lon - asc))
        return c + r * math.cos(ang), c - r * math.sin(ang)

    parts = [
        f'<svg viewBox="0 0 {2 * c} {2 * c}" class="h-auto w-full" role="img" aria-label="Двойная карта партнёров">',
        f'<circle cx="{c}" cy="{c}" r="{r_zod_o}" fill="var(--color-paper)" stroke="var(--color-ink)" stroke-width="1.5"/>',
        f'<circle cx="{c}" cy="{c}" r="{r_zod_i}" fill="none" stroke="var(--color-ink)" stroke-width="1"/>',
        f'<circle cx="{c}" cy="{c}" r="{r_core}" fill="var(--color-milk)" stroke="var(--color-line)"/>',
    ]
    for k in range(12):
        x1, y1 = xy(k * 30, r_zod_i)
        x2, y2 = xy(k * 30, r_zod_o)
        gx, gy = xy(k * 30 + 15, (r_zod_i + r_zod_o) / 2)
        fill = ["var(--color-a-soft)", "var(--color-sage-soft)", "var(--color-b-soft)", "var(--color-lilac-soft)"][k % 4]
        a0, a1 = math.radians(180 - (k * 30 - asc)), math.radians(180 - (k * 30 + 30 - asc))
        parts.append(
            f'<path d="M{c + r_zod_i * math.cos(a0):.1f} {c - r_zod_i * math.sin(a0):.1f} L{c + r_zod_o * math.cos(a0):.1f} {c - r_zod_o * math.sin(a0):.1f} '
            f"A{r_zod_o} {r_zod_o} 0 0 0 {c + r_zod_o * math.cos(a1):.1f} {c - r_zod_o * math.sin(a1):.1f} L{c + r_zod_i * math.cos(a1):.1f} {c - r_zod_i * math.sin(a1):.1f} "
            f'A{r_zod_i} {r_zod_i} 0 0 1 {c + r_zod_i * math.cos(a0):.1f} {c - r_zod_i * math.sin(a0):.1f}Z" fill="{fill}" opacity=".7"/>'
        )
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="var(--color-ink)" stroke-width="1"/>')
        parts.append(
            f'<text x="{gx:.1f}" y="{gy + 5:.1f}" text-anchor="middle" font-size="15" fill="var(--color-ink)">{SIGN_GLYPHS[k]}</text>'
        )
    for i, cusp in enumerate(astro.houses_a):
        x1, y1 = xy(cusp, r_core)
        x2, y2 = xy(cusp, r_zod_i)
        heavy = i in (0, 3, 6, 9)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="var(--color-ink)" stroke-width="{1.6 if heavy else 0.6}" stroke-dasharray="{"" if heavy else "2 3"}"/>'
        )
        nx, ny = xy(cusp + 6, r_core + 9)
        parts.append(
            f'<text x="{nx:.1f}" y="{ny + 3:.1f}" text-anchor="middle" font-size="8" fill="var(--color-ink-3)" font-family="var(--font-mono)">{i + 1}</text>'
        )
    pos_a = {p.name: p.lon for p in astro.planets_a}
    pos_b = {p.name: p.lon for p in astro.planets_b}
    for asp in astro.all_aspects:
        if not asp.major or asp.planet_a not in pos_a or asp.planet_b not in pos_b:
            continue
        x1, y1 = xy(pos_a[asp.planet_a], r_core - 4)
        x2, y2 = xy(pos_b[asp.planet_b], r_core - 4)
        color = {"synergy": "var(--color-synergy)", "attention": "var(--color-attention)"}.get(asp.tone, "var(--color-ink-3)")
        parts.append(
            f'<line class="wheel-asp" data-hover-target="asp-{escape(asp.key)}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{2.2 if asp.double else 1.2}" opacity=".75"/>'
        )
    for rows, r, color in ((astro.planets_a, r_a, "var(--color-a)"), (astro.planets_b, r_b, "var(--color-b)")):
        placed: list[float] = []
        for p in rows:
            lon = p.lon
            while any(abs(((lon - q + 180) % 360) - 180) < 7 for q in placed):
                lon += 7  # spread glyphs that sit on top of each other
            placed.append(lon)
            x, y = xy(lon, r)
            tx, ty = xy(p.lon, r_zod_i - 2)
            parts.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{color}" stroke-width="1" opacity=".5"/>')
            glyph = escape(p.glyph or p.name[:2])
            size = 9 if len(p.glyph) > 1 else 15
            parts.append(
                f'<g><title>{escape(p.name)} · {escape(p.sign)} {escape(p.degree)}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="var(--color-paper)" stroke="{color}" stroke-width="2"/>'
                f'<text x="{x:.1f}" y="{y + size / 3:.1f}" text-anchor="middle" font-size="{size}" fill="var(--color-ink)">{glyph}</text></g>'
            )
    parts.append("</svg>")
    return mark_safe("".join(parts))


@register.simple_tag
def aspect_matrix(astro) -> dict:
    """Rows: A's points, columns: B's points, cells: the aspect between them (major preferred)."""
    cells: dict[tuple[str, str], object] = {}
    for asp in astro.all_aspects:
        key = (asp.planet_a, asp.planet_b)
        if key not in cells or (asp.major and not cells[key].major):  # type: ignore[attr-defined]
            cells[key] = asp
    cols = [p for p in astro.planets_b]
    return {"cols": cols, "rows": [(p, [cells.get((p.name, q.name)) for q in cols]) for p in astro.planets_a]}


@register.filter
def safe_json(value) -> str:
    import json

    return mark_safe(json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace('"', "&quot;"))


@register.filter
def universe_glyph(universe: str) -> str:
    return {"astrology": "orbit", "psychology": "brain", "numerology": "hash", "tarot": "layers"}.get(universe, "sparkles")


@register.filter(name="gen")
def gen_filter(name: str) -> str:
    from apps.core.domain.names import gen

    return gen(name)


@register.filter
def tab_active(tab: str, key: str) -> bool:
    """The «layers» tab stays lit while the reader is inside one of the layers."""
    return tab == key or (key == "layers" and tab in ("astrology", "psychology", "numbers", "tarot"))


@register.simple_tag
def sprite_url() -> str:
    return _sprite_url()


@register.filter
def device_label(ua: str) -> str:
    """«iPhone · Safari» from a user agent — enough to recognise your own devices."""
    os_ = next(
        (
            n
            for k, n in [
                ("iPhone", "iPhone"),
                ("iPad", "iPad"),
                ("Android", "Android"),
                ("Mac OS X", "Mac"),
                ("Windows", "Windows"),
                ("Linux", "Linux"),
            ]
            if k in ua
        ),
        "Устройство",
    )
    br = next(
        (
            n
            for k, n in [
                ("YaBrowser", "Яндекс Браузер"),
                ("Edg/", "Edge"),
                ("Firefox", "Firefox"),
                ("Chrome", "Chrome"),
                ("Safari", "Safari"),
            ]
            if k in ua
        ),
        "",
    )
    return f"{os_} · {br}" if br else os_


@register.simple_tag
def qr_svg(data: str) -> str:
    """Inline SVG QR code for invite links; scales with its box and follows the text colour."""
    import segno

    svg = segno.make(data, error="m").svg_inline(scale=1, border=2, dark="#000", light=None, omitsize=True)
    svg = svg.replace('stroke="#000"', 'stroke="currentColor"')  # segno validates colours; recolour after
    return mark_safe(svg.replace("<svg ", '<svg class="h-full w-full" ', 1))


@register.filter(name="acc")
def acc_filter(name: str) -> str:
    """Accusative: «пригласить Тасю»."""
    from apps.core.domain.names import forms

    return forms(name)["_acc"]
