"""Post-validator for LLM stitching (prompt §4.4): pure code, no model in the loop."""

import re
from dataclasses import dataclass

FORBIDDEN = [
    r"нельзя\s+быть\s+вместе",
    r"расста(нь|ва)тесь",
    r"обречен",
    r"диагноз",
    r"гарантир",
    r"судьба\s+решил",
    r"измен(а|ит|ят)",
    r"беременн",
    r"смерт",
    r"болезн",
    r"разбогате",
    r"вселенная\s+вед[её]т",
    r"учёные\s+доказали",
]
PLANETS = ["Солнце", "Луна", "Меркурий", "Венера", "Марс", "Юпитер", "Сатурн", "Уран", "Нептун", "Плутон", "Хирон", "Лилит"]
_FORBIDDEN = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN]


@dataclass
class Verdict:
    ok: bool
    errors: list[str]


def check_paragraph(
    text: str, block_ids: list[str], allowed_ids: set[str], allowed_numbers: set[str], allowed_planets: set[str]
) -> list[str]:
    errors = []
    if not block_ids:
        errors.append("абзац без block_ids")
    unknown = [b for b in block_ids if b not in allowed_ids]
    if unknown:
        errors.append(f"неизвестные block_ids: {unknown}")
    for rx in _FORBIDDEN:
        if rx.search(text):
            errors.append(f"запрещённая формулировка: «{rx.pattern}»")
    for n in re.findall(r"\d+(?:[.,]\d+)?", text):
        if n.replace(",", ".") not in allowed_numbers:
            errors.append(f"число не из расчёта: {n}")
    for planet in PLANETS:
        if re.search(rf"\b{planet[:-1]}", text) and planet not in allowed_planets:
            errors.append(f"планета не из расчёта: {planet}")
    return errors
