"""Brand illustration: duotone glyphs for universes/categories and generative posters for pair types.

All shapes are original, flat fills with an ink outline — the same sticker language as the arcana emblems.
"""

import math as _m

from django import template
from django.utils.safestring import mark_safe

from apps.compatibility.domain.archetypes import ROLES, dynamic_for
from apps.web.templatetags.ui import icon

register = template.Library()

INK = 'stroke="var(--color-ink)" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"'
A, B, PAIR, SAGE, LILAC, PAPER = (
    "var(--color-a)",
    "var(--color-b)",
    "var(--color-pair)",
    "var(--color-sage)",
    "var(--color-lilac)",
    "var(--color-paper)",
)

GLYPHS = {
    # universes
    "orbit": f'<ellipse cx="16" cy="16" rx="13.5" ry="6" fill="none" {INK} transform="rotate(-25 16 16)"/><circle cx="16" cy="16" r="6" fill="{B}" {INK}/>'
    f'<circle cx="27.8" cy="10.4" r="2.2" fill="var(--color-ink)"/><path d="M6.5 4.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" fill="var(--color-ink)"/>',
    "brain": f'<circle cx="16" cy="16" r="12" fill="{SAGE}" {INK}/><path d="M7.5 16.5h3l2-5 3 10 2.5-7 2 2h4.5" fill="none" {INK}/>',
    "hash": f'<rect x="4.5" y="4.5" width="23" height="23" rx="6" fill="{PAPER}" {INK}/><path d="M10.5 10.5 21.5 21.5" fill="none" {INK}/>'
    f'<circle cx="10.5" cy="10.5" r="3.4" fill="{A}" {INK}/><circle cx="21.5" cy="21.5" r="3.4" fill="{A}" {INK}/>'
    + "".join(
        f'<circle cx="{x}" cy="{y}" r="1.3" fill="var(--color-ink)"/>'
        for x, y in [(16, 10.5), (21.5, 10.5), (10.5, 16), (16, 16), (21.5, 16), (10.5, 21.5), (16, 21.5)]
    ),
    "layers": f'<rect x="5" y="7.5" width="12.5" height="18.5" rx="2.6" fill="{PAPER}" {INK} transform="rotate(-12 11.25 16.75)"/>'
    f'<rect x="14" y="5.5" width="12.5" height="18.5" rx="2.6" fill="{PAIR}" {INK} transform="rotate(10 20.25 14.75)"/>'
    f'<path d="M20.2 10.5l1 2.6 2.6 1-2.6 1-1 2.6-1-2.6-2.6-1 2.6-1z" fill="var(--color-ink)" transform="rotate(10 20.25 14.75)"/>',
    # categories
    "flame": f'<path d="M16 3.5c1.2 5 7.5 7 7.5 14.5a7.5 7.5 0 0 1-15 0c0-4.3 2.2-6.5 3.2-8.6 1 3 2.3 4.3 3.3 4.3 0-4.2-.2-7.3 1-10.2z" fill="{A}" {INK}/>'
    f'<path d="M16 17.5c1.2 2 3.2 3 3.2 5.2a3.2 3.2 0 0 1-6.4 0c0-2.1 2-3.1 3.2-5.2z" fill="{PAIR}" {INK}/>',
    "heart": f'<path d="M16 27s-11.5-6.6-11.5-14.4A6.2 6.2 0 0 1 16 9.2a6.2 6.2 0 0 1 11.5 3.4C27.5 20.4 16 27 16 27z" fill="{A}" {INK}/>'
    f'<path d="M9.5 12.5a3 3 0 0 1 3-2.6" fill="none" stroke="var(--color-paper)" stroke-width="1.7" stroke-linecap="round"/>',
    "message-circle": f'<path d="M3.5 8a4 4 0 0 1 4-4h11a4 4 0 0 1 4 4v6a4 4 0 0 1-4 4h-7.5l-5 4v-4.4A4 4 0 0 1 3.5 14z" fill="{PAPER}" {INK}/>'
    f'<path d="M11.5 16.5a4 4 0 0 1 4-4h9a4 4 0 0 1 4 4v5a4 4 0 0 1-4 4v4l-5-4h-4a4 4 0 0 1-4-4z" fill="{B}" {INK}/>'
    f'<circle cx="16.5" cy="19" r="1.1" fill="var(--color-paper)"/><circle cx="20" cy="19" r="1.1" fill="var(--color-paper)"/><circle cx="23.5" cy="19" r="1.1" fill="var(--color-paper)"/>',
    "gem": f'<path d="M5.5 12.5 10.5 6h11l5 6.5L16 27z" fill="{PAIR}" {INK}/><path d="M5.5 12.5h21M10.5 6l3 6.5L16 27l2.5-14.5 3-6.5" fill="none" {INK}/>',
    "shield-check": f'<path d="M16 3.5 26 7.5v7c0 7.2-5 11.4-10 13.3C11 25.9 6 21.7 6 14.5v-7z" fill="{SAGE}" {INK}/><path d="m11.5 15.5 3 3 6-6.5" fill="none" {INK}/>',
    "house": f'<path d="M8 13.5V26.5h16V13.5" fill="{LILAC}" {INK}/><path d="M4.5 15 16 5.5 27.5 15" fill="none" {INK}/>'
    f'<rect x="13.5" y="18.5" width="5" height="8" rx="1.2" fill="{PAPER}" {INK}/>',
}


@register.simple_tag
def glyph(name: str, cls: str = "size-8") -> str:
    body = GLYPHS.get(name)
    if body is None:
        return icon(name, cls)
    return mark_safe(f'<svg viewBox="0 0 32 32" class="glyph {cls} shrink-0" aria-hidden="true">{body}</svg>')


# ── pair-type posters (300 × 375) ──────────────────────────────────────────
S3 = 'stroke="var(--color-ink)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"'
WAVES = "".join(
    f'<path class="p-wave" style="--i:{k}" d="M-20 {300 + k * 22} q 25 -12 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0" fill="none" {S3}/>'
    for k in range(3)
)

POSTERS = {
    "compass": (
        "var(--color-b-soft)",
        f'<circle cx="236" cy="78" r="26" fill="{PAIR}" {S3} class="p-pulse"/>'
        f'<path d="M188 52v196" {S3}/><path class="p-sway" d="M194 62c40 40 66 110 66 176H194z" fill="{A}" {S3}/>'
        f'<path d="M150 250h130l-22 34h-92z" fill="{PAPER}" {S3}/>'
        f'<circle cx="104" cy="204" r="70" fill="{PAPER}" {S3}/><circle cx="104" cy="204" r="54" fill="none" stroke="var(--color-ink)" stroke-width="1.6" stroke-dasharray="2 7"/>'
        f'<g class="p-spin-slow" style="transform-origin:104px 204px"><path d="M104 146l13 58-13 58-13-58z" fill="{B}" {S3}/><path d="M104 146l13 58H91z" fill="{A}" {S3}/></g>'
        f'<circle cx="104" cy="204" r="6" fill="{PAPER}" {S3}/>' + WAVES,
    ),
    "fire": (
        "var(--color-pair-soft)",
        f'<path d="M30 300h240" {S3}/>'
        f'<g class="p-flicker" style="transform-origin:110px 300px"><path d="M110 120c8 34 52 48 52 104a52 52 0 0 1-104 0c0-30 15-46 22-60 7 21 16 30 23 30 0-30-1-50 7-74z" fill="{A}" {S3}/>'
        f'<path d="M110 220c8 13 22 20 22 35a22 22 0 0 1-44 0c0-14 14-21 22-35z" fill="{PAIR}" {S3}/></g>'
        f'<g class="p-flicker" style="transform-origin:198px 300px;animation-delay:-.8s"><path d="M198 92c8 38 56 54 56 116a58 58 0 0 1-116 0c0-33 17-51 25-66 7 23 18 33 25 33 0-34-1-55 10-83z" fill="{B}" {S3}/>'
        f'<path d="M198 210c9 14 24 22 24 39a24 24 0 0 1-48 0c0-16 15-24 24-39z" fill="{PAIR}" {S3}/></g>'
        + "".join(
            f'<circle class="p-rise" style="--i:{k}" cx="{x}" cy="{y}" r="{r}" fill="var(--color-ink)"/>'
            for k, (x, y, r) in enumerate([(150, 90, 4), (176, 60, 3), (128, 66, 3.5), (210, 40, 2.5)])
        ),
    ),
    "bridge": (
        "var(--color-sage-soft)",
        f'<circle cx="150" cy="96" r="34" fill="{PAIR}" {S3} class="p-pulse"/>'
        f'<path d="M24 236c40-90 212-90 252 0" fill="none" {S3} stroke-width="14" stroke="var(--color-ink)"/><path d="M24 236c40-90 212-90 252 0" fill="none" stroke="{A}" stroke-width="8" stroke-linecap="round"/>'
        f'<path d="M70 196v74M230 196v74M150 168v102" {S3}/>' + WAVES.replace('fill="none"', 'fill="none"', 1),
    ),
    "spark": (
        "var(--color-a-soft)",
        f'<g class="p-spin" style="transform-origin:150px 200px"><path d="M150 200m-110 0a110 110 0 1 0 220 0a86 86 0 1 0-172 0a62 62 0 1 0 124 0a38 38 0 1 0-76 0" fill="none" stroke="{B}" stroke-width="12" stroke-linecap="round"/>'
        f'<path d="M150 200m-110 0a110 110 0 1 0 220 0a86 86 0 1 0-172 0a62 62 0 1 0 124 0a38 38 0 1 0-76 0" fill="none" {S3} stroke-width="2"/></g>'
        f'<path class="p-pulse" style="transform-origin:150px 200px" d="M150 120l20 60 60 20-60 20-20 60-20-60-60-20 60-20z" fill="{PAIR}" {S3}/>',
    ),
    "harbor": (
        "var(--color-b-soft)",
        f'<path class="p-rise-sun" d="M60 250a90 90 0 0 1 180 0z" fill="{PAIR}" {S3}/>'
        f'<path d="M20 250h260" {S3}/><path class="p-sway" d="M196 196v40M196 200l26 28h-26z" fill="{A}" {S3}/><path d="M178 238h46l-8 12h-30z" fill="{PAPER}" {S3}/>'
        + WAVES,
    ),
    "explorers": (
        "var(--color-lilac-soft)",
        f'<path d="M20 300 112 128l92 172z" fill="{A}" {S3}/><path d="M118 300l86-150 86 150z" fill="{B}" {S3}/>'
        f'<path d="M204 150V96" {S3}/><path class="p-wave-flag" d="M204 98h40l-10 12 10 12h-40z" fill="{PAIR}" {S3}/>'
        f'<path d="M40 330c40-20 90 10 130-6s70-20 110-10" fill="none" stroke="var(--color-ink)" stroke-width="3" stroke-dasharray="2 10" stroke-linecap="round"/>'
        f'<path class="p-pulse" d="M70 70l5 14 14 5-14 5-5 14-5-14-14-5 14-5z" fill="var(--color-ink)"/>',
    ),
}


@register.simple_tag
def poster(key: str, cls: str = "w-full") -> str:
    bg, body = POSTERS.get(key, POSTERS["compass"])
    return mark_safe(
        f'<svg viewBox="0 0 300 375" class="poster {cls}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
        f'<rect width="300" height="375" fill="{bg}"/>{body}</svg>'
    )


# ── role emblems (120 × 120) and generated pair portraits ─────────────────


def _star(cx: float, cy: float, R: float, r: float, n: int = 5) -> str:
    pts = []
    for k in range(n * 2):
        rad, a = (R if k % 2 == 0 else r), _m.pi / n * k - _m.pi / 2
        pts.append(f"{cx + rad * _m.cos(a):.1f},{cy + rad * _m.sin(a):.1f}")
    return " ".join(pts)


def _emblem(key: str, c: str) -> str:
    P = PAIR
    return {
        "spark": f'<path d="M60 12l11 37 37 11-37 11-11 37-11-37-37-11 37-11z" fill="{c}" {S3}/><circle cx="98" cy="22" r="4.5" fill="var(--color-ink)"/><circle cx="22" cy="98" r="3.5" fill="var(--color-ink)"/><circle cx="100" cy="96" r="2.5" fill="var(--color-ink)"/>',
        "fire": f'<path d="M60 10c6 27 40 37 40 78a40 40 0 0 1-80 0c0-23 12-35 17-46 5 16 12 23 18 23 0-23-1-38 5-55z" fill="{c}" {S3}/><path d="M60 76c6 10 17 16 17 28a17 17 0 0 1-34 0c0-12 11-17 17-28z" fill="{P}" {S3}/>',
        "star": f'<circle cx="60" cy="62" r="54" fill="none" stroke="var(--color-ink)" stroke-width="2" stroke-dasharray="3 7"/><polygon points="{_star(60, 64, 46, 19)}" fill="{c}" {S3}/>',
        "compass": f'<circle cx="60" cy="60" r="50" fill="{PAPER}" {S3}/><circle cx="60" cy="60" r="39" fill="none" stroke="var(--color-ink)" stroke-width="1.8" stroke-dasharray="2 7"/><path d="M60 16l12 44-12 44-12-44z" fill="{PAPER}" {S3}/><path d="M60 16l12 44H48z" fill="{c}" {S3}/><circle cx="60" cy="60" r="6" fill="{PAPER}" {S3}/>',
        "mountain": f'<path d="M8 106 52 28l20 34 10-14 30 58z" fill="{c}" {S3}/><path d="M52 28l12 21-7-4-5 7-6-7-6 4z" fill="{PAPER}" {S3}/><path d="M2 106h116" {S3}/>',
        "garden": f'<path d="M60 108V56" {S3}/><path d="M60 78c-26 2-38-15-38-32 23 0 38 13 38 32z" fill="{c}" {S3}/><path d="M60 64c4-24 23-36 42-34 0 23-19 36-42 34z" fill="{P}" {S3}/><circle cx="60" cy="48" r="9" fill="{c}" {S3}/><path d="M28 108h64" {S3}/>',
        "bridge": f'<path d="M8 94c18-58 86-58 104 0" fill="none" stroke="var(--color-ink)" stroke-width="13" stroke-linecap="round"/><path d="M8 94c18-58 86-58 104 0" fill="none" stroke="{c}" stroke-width="7" stroke-linecap="round"/><path d="M30 76v32M90 76v32M60 58v50M2 108h116" {S3}/>',
        "lighthouse": f'<path d="M72 34 114 20v28z" fill="{P}" opacity=".75"/><path d="M48 34 6 20v28z" fill="{P}" opacity=".75"/><path d="M45 108l7-66h16l7 66z" fill="{PAPER}" {S3}/><path d="M47 94l2-16h22l2 16z" fill="{c}" {S3}/><path d="M50 66l1-12h18l1 12z" fill="{c}" {S3}/><rect x="50" y="30" width="20" height="12" fill="{P}" {S3}/><path d="M46 30l14-14 14 14z" fill="{c}" {S3}/><path d="M30 108h60" {S3}/>',
        "wind": f'<path d="M12 44h58a15 15 0 1 0-15-15" fill="none" stroke="{c}" stroke-width="9" stroke-linecap="round"/><path d="M12 64h80a15 15 0 1 1-15 15" fill="none" stroke="{c}" stroke-width="9" stroke-linecap="round"/><path d="M22 84h36a11 11 0 1 1-11 11" fill="none" stroke="{c}" stroke-width="9" stroke-linecap="round"/>'
        f'<path d="M12 44h58a15 15 0 1 0-15-15M12 64h80a15 15 0 1 1-15 15M22 84h36a11 11 0 1 1-11 11" fill="none" stroke="var(--color-ink)" stroke-width="2.4" stroke-linecap="round"/><path d="M92 32c9-8 20-3 20 6-9 6-19 3-20-6z" fill="{P}" {S3}/>',
        "river": f'<circle cx="60" cy="60" r="50" fill="{c}" {S3}/>'
        + "".join(
            f'<path d="M18 {y} q10.5-9 21 0 t21 0 t21 0 t21 0" fill="none" stroke="{PAPER}" stroke-width="5" stroke-linecap="round"/>'
            for y in (46, 62, 78)
        ),
        "harbor": f'<circle cx="60" cy="62" r="52" fill="{c}" {S3}/><circle cx="60" cy="27" r="9" fill="{PAPER}" stroke="var(--color-ink)" stroke-width="4.5"/><path d="M60 36v66M42 50h36M24 78c4 17 19 26 36 26s32-9 36-26M24 78l-7 9M24 78l10 3M96 78l7 9M96 78l-10 3" fill="none" stroke="var(--color-ink)" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>',
        "sail": f'<path d="M58 10v88" {S3}/><path d="M62 14c27 22 42 54 42 84H62z" fill="{c}" {S3}/><path d="M54 34 22 92h32z" fill="{P}" {S3}/><path d="M14 100h92l-13 16H27z" fill="{PAPER}" {S3}/>',
    }[key]


# placement per dynamic: (bg fills, decoration, A transform, B transform)
_LAYOUT = {
    "resonance": (
        "var(--color-pair-soft)",
        '<circle cx="150" cy="200" r="138" fill="none" stroke="var(--color-ink)" stroke-width="2.5" stroke-dasharray="4 9"/>',
        (14, 132, 1.15),
        (148, 132, 1.15),
    ),
    "complement": (
        "var(--color-a-soft)",
        f'<path d="M0 205c60-40 120 40 180 0s90-40 120-20V375H0z" fill="var(--color-b-soft)"/><path d="M0 205c60-40 120 40 180 0s90-40 120-20" fill="none" {S3}/>',
        (30, 34, 1.3),
        (124, 196, 1.3),
    ),
    "contrast": (
        "var(--color-a-soft)",
        f'<path d="M300 0V375H0z" fill="var(--color-b-soft)"/><path d="M300 0 0 375" fill="none" {S3}/><path class="p-pulse" d="M128 172l26-6-10 18 26-4-30 30 8-20-24 4z" fill="{PAIR}" {S3}/>',
        (16, 26, 1.2),
        (148, 214, 1.2),
    ),
    "friction": (
        "var(--color-sage-soft)",
        '<path d="M70 120c40 60 120 10 150 80s-60 80-30 120" fill="none" stroke="var(--color-ink)" stroke-width="3" stroke-dasharray="2 10" stroke-linecap="round"/>',
        (24, 30, 1.2),
        (140, 200, 1.2),
    ),
}


def pair_poster_svg(role_a: str, role_b: str, cls: str = "w-full") -> str:
    a, b = ROLES[role_a], ROLES[role_b]
    bg, deco, (ax, ay, asc), (bx, by, bsc) = _LAYOUT[dynamic_for(a, b).key]
    dust = "".join(
        f'<circle class="p-rise" style="--i:{k}" cx="{x}" cy="{y}" r="{r}" fill="var(--color-ink)"/>'
        for k, (x, y, r) in enumerate([(250, 52, 3.5), (36, 330, 3), (268, 300, 2.5), (150, 30, 2.5)])
    )
    return (
        f'<svg viewBox="0 0 300 375" class="poster {cls}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
        f'<rect width="300" height="375" fill="{bg}"/>{deco}{dust}'
        f'<g transform="translate({ax} {ay}) scale({asc})"><g class="p-float-a">{_emblem(a.key, A)}</g></g>'
        f'<g transform="translate({bx} {by}) scale({bsc})"><g class="p-float-b">{_emblem(b.key, B)}</g></g></svg>'
    )


@register.simple_tag
def pair_poster(role_a: str, role_b: str, cls: str = "w-full") -> str:
    return mark_safe(pair_poster_svg(role_a, role_b, cls))


@register.simple_tag
def role_emblem(key: str, side: str = "a", cls: str = "size-16") -> str:
    color = {"a": A, "b": B}.get(side, PAIR)
    return mark_safe(f'<svg viewBox="-4 -4 128 128" class="{cls} shrink-0" aria-hidden="true">{_emblem(key, color)}</svg>')
