# ruff: noqa: E501 — SVG drawing data reads best one shape per line
"""Profile avatars people pick for themselves: flat shapes with an ink outline, like the share card art.

Each is the inside of a 64×64 SVG; the round background comes from `render`. Colours are the app palette.
"""

from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

INK, CORAL, BLUE, SUN, SAGE, LILAC, CREAM = "#1e1a16", "#f2865c", "#5470ee", "#f4c84f", "#7fae8e", "#b9a7f2", "#fffaf2"
_S = f'stroke="{INK}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"'

# key: (title, background, shapes)
AVATARS: dict[str, tuple[str, str, str]] = {
    "sun": ("Солнце", "#ffe6da", f'<g {_S}>' + "".join(
        f'<path d="M32 9v6" transform="rotate({a} 32 32)" fill="none"/>' for a in range(0, 360, 45)
    ) + f'<circle cx="32" cy="32" r="12" fill="{SUN}"/></g>'),
    "moon": ("Луна", "#e1e7ff", f'<g {_S}><path d="M38 14a19 19 0 1 0 12 30A15 15 0 0 1 38 14Z" fill="{SUN}"/>'
             f'<circle cx="19" cy="20" r="1.8" fill="{INK}" stroke="none"/><circle cx="47" cy="20" r="1.4" fill="{INK}" stroke="none"/></g>'),
    "star": ("Звезда", "#ece6ff", f'<g {_S}><path d="M32 12l5.6 12.6 13.4 1.4-10 9.2 2.9 13.3L32 41.6 20.1 48.5 23 35.2l-10-9.2 13.4-1.4Z" fill="{SUN}"/></g>'),
    "flame": ("Огонь", "#fff1d6", f'<g {_S}><path d="M32 10c6 9 15 14 15 26a15 15 0 0 1-30 0c0-7 4-11 6-15 1 4 3 6 5 7 0-7 1-12 4-18Z" fill="{CORAL}"/>'
              f'<path d="M32 33c3 4 6 6 6 10a6 6 0 0 1-12 0c0-4 3-6 6-10Z" fill="{SUN}"/></g>'),
    "wave": ("Волна", "#e1e7ff", f'<g {_S}><path d="M10 34c4-4 7-4 11 0s7 4 11 0 7-4 11 0 7 4 11 0v10c0 6-10 12-22 12S10 50 10 44Z" fill="{BLUE}"/>'
             f'<path d="M14 45c3-3 6-3 9 0s6 3 9 0 6-3 9 0 6 3 9 0" fill="none" stroke="{CREAM}"/><circle cx="22" cy="18" r="5" fill="{SUN}"/></g>'),
    "sprout": ("Росток", "#e3efe6", f'<g {_S}><path d="M32 52V30" fill="none"/><path d="M32 34c-12 0-18-7-18-16 10 0 18 6 18 16Z" fill="{SAGE}"/>'
               f'<path d="M32 30c0-9 7-15 18-15 0 10-7 15-18 15Z" fill="{SAGE}"/><path d="M20 52h24" fill="none"/></g>'),
    "mountain": ("Гора", "#e3efe6", f'<g {_S}><path d="M8 50 25 20l9 15 6-9 16 24Z" fill="{SAGE}"/><path d="M25 20l-5 9 4-2 3 3 3-3 4 3Z" fill="{CREAM}"/>'
                 f'<circle cx="46" cy="16" r="5" fill="{SUN}"/></g>'),
    "anchor": ("Якорь", "#e1e7ff", f'<g {_S}><circle cx="32" cy="15" r="5" fill="{CREAM}"/><path d="M32 20v30M22 28h20" fill="none"/>'
               f'<path d="M14 38c2 8 9 12 18 12s16-4 18-12" fill="none"/><path d="M11 40l3-4 4 3M53 40l-3-4-4 3" fill="none"/></g>'),
    "planet": ("Планета", "#ece6ff", f'<g {_S}><circle cx="32" cy="32" r="13" fill="{LILAC}"/>'
               f'<path d="M12 40c-3-5 6-11 20-15s24-3 24 2-8 9-20 13-21 4-24 0Z" fill="none"/><circle cx="48" cy="14" r="2" fill="{SUN}"/></g>'),
    "flower": ("Цветок", "#ffe6da", f'<g {_S}>' + "".join(
        f'<ellipse cx="32" cy="19" rx="7" ry="10" fill="{CORAL}" transform="rotate({a} 32 32)"/>' for a in range(0, 360, 72)
    ) + f'<circle cx="32" cy="32" r="7" fill="{SUN}"/></g>'),
    "bird": ("Птица", "#fbf0c9", f'<g {_S}><path d="M10 30l9 5" fill="none"/><path d="M14 36c0-9 9-15 19-13l5-5c4-3 10-1 11 4l6 2-6 3c0 12-9 19-21 19-8 0-14-4-14-10Z" fill="{BLUE}"/>'
             f'<path d="M21 37c6 3 13 1 16-6" fill="none" stroke="{CREAM}"/><circle cx="44" cy="23" r="1.9" fill="{INK}" stroke="none"/></g>'),
    "cloud": ("Облако", "#e1e7ff", f'<g {_S}><path d="M18 44a9 9 0 0 1 1-18 13 13 0 0 1 25-3 10 10 0 0 1 3 21Z" fill="{CREAM}"/>'
              f'<path d="M24 50l-2 5M33 50l-2 5M42 50l-2 5" fill="none" stroke="{BLUE}"/></g>'),
    "cat": ("Кот", "#fbf0c9", f'<g {_S}><path d="M16 50V22l8 7h16l8-7v28Z" fill="{CORAL}"/>'
            f'<circle cx="26" cy="37" r="2" fill="{INK}" stroke="none"/><circle cx="38" cy="37" r="2" fill="{INK}" stroke="none"/>'
            f'<path d="M30 42h4l-2 2Z" fill="{INK}"/><path d="M10 40h8M10 45h8M46 40h8M46 45h8" fill="none"/></g>'),
    "key": ("Ключ", "#ece6ff", f'<g {_S}><circle cx="22" cy="24" r="10" fill="{SUN}"/><circle cx="22" cy="24" r="3.5" fill="{CREAM}"/>'
            f'<path d="M29 31l20 20M42 44l-5 5M47 49l-4 4" fill="none"/></g>'),
}  # fmt: skip
DEFAULT = "sun"


def render(key: str | None, size: int = 40, cls: str = "") -> SafeString:
    """An avatar as inline SVG; an unknown key falls back to the default."""
    title, bg, shapes = AVATARS.get(key or "", AVATARS[DEFAULT])
    return format_html(
        '<svg class="avatar {}" width="{}" height="{}" viewBox="0 0 64 64" role="img" aria-label="{}">'
        '<circle cx="32" cy="32" r="31" fill="{}"/>{}</svg>',
        cls, size, size, title, bg, mark_safe(shapes),  # noqa: S308 — the shapes are our own constants above
    )  # fmt: skip
