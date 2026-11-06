"""Prune the Lucide sprite (~550 KB) to the icons the templates actually use."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "node_modules/lucide-static/sprite.svg"
OUT = ROOT / "static/icons/sprite.svg"

used = set()
maybe: set[str] = set()
for f in [*ROOT.glob("templates/**/*.html"), *ROOT.glob("apps/**/*.py"), *ROOT.glob("apps/**/*.json")]:
    text = f.read_text(encoding="utf-8")
    used |= set(re.findall(r"""{%\s*icon\s+['"]([\w-]+)['"]""", text))
    used |= set(re.findall(r'"icon":\s*"([\w-]+)"', text))
    used |= set(re.findall(r"""icon=['"]([\w-]+)['"]""", text))
    if f.parent.name == "web" and f.suffix == ".py":  # nav/tab tuples in views.py and context.py — kept only if such an icon exists
        maybe |= set(re.findall(r'"([a-z][a-z-]+)"', text))
    used |= set(re.findall(r"""toast\([^)]*,\s*'([\w-]+)'\)""", text))
used |= {
    "check",
    "minus",
    "eye",
    "triangle-exclamation-point",
    "sparkles",
    "trending-up",
    "trending-down",
    "chevron-down",
    "circle-question-mark",
    "flask-conical",
}

sprite = SRC.read_text(encoding="utf-8")
symbols = {m.group(1): m.group(0) for m in re.finditer(r'(?s)<symbol id="([\w-]+)".*?</symbol>', sprite)}
missing = sorted(used - symbols.keys())
used |= maybe & symbols.keys()
OUT.write_text(
    '<svg xmlns="http://www.w3.org/2000/svg">' + "".join(symbols[n] for n in sorted(used & symbols.keys())) + "</svg>", encoding="utf-8"
)
print(f"icons: {len(used & symbols.keys())} kept, {OUT.stat().st_size // 1024} KB")
if missing:
    sys.exit(f"missing icons: {', '.join(missing)}")
