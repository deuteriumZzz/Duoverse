"""«Погода пары»: this week's sky against both natal charts — symbolic, like the rest of astrology here. Only the
planets that change over days (Venus, Mars, Mercury) and only tight aspects, so the note really is about this week.
"""

ORB = 2.5
ASPECTS = {0: "☌", 60: "⚹", 90: "□", 120: "△", 180: "☍"}
SOFT = {0, 60, 120}
NATAL = ("Солнце", "Венера", "Марс")  # date-only charts are reliable for these; the Moon needs a birth time
NOTES = {
    "Венера": ("хорошее время для свиданий, нежности и маленьких подарков", "легко обидеться на мелочь — проговаривайте ожидания"),
    "Марс": ("много сил на общие дела и близость", "споры вспыхивают быстрее — договоритесь о паузе заранее"),
    "Меркурий": ("удачные дни, чтобы обсудить планы и договориться", "легко понять друг друга не так — переспрашивайте"),
}


def weather(sky: dict[str, float], natal: list[tuple[str, dict[str, float]]], top: int = 3) -> list[dict]:
    """natal: [(name, planets)]; → [{"planet", "glyph", "point", "who", "tone", "text", "orb"}], tightest first."""
    hits = []
    for planet, (soft_note, hard_note) in NOTES.items():
        for who, planets in natal:
            for point in NATAL:
                if point not in planets or planet not in sky:
                    continue
                gap = abs((sky[planet] - planets[point] + 180) % 360 - 180)  # same distance as chart.synastry
                for angle, glyph in ASPECTS.items():
                    if abs(gap - angle) <= ORB:
                        soft = angle in SOFT
                        hits.append({"planet": planet, "glyph": glyph, "point": point, "who": who,
                                     "tone": "synergy" if soft else "attention", "text": soft_note if soft else hard_note,
                                     "orb": round(abs(gap - angle), 1)})  # fmt: skip
    return sorted(hits, key=lambda h: h["orb"])[:top]


if __name__ == "__main__":
    sky = {"Венера": 100.0, "Марс": 10.0, "Меркурий": 200.0}
    w = weather(sky, [("Аня", {"Солнце": 220.5, "Венера": 13.0, "Марс": 0.0}), ("Миша", {"Солнце": 199.0, "Венера": 300.0, "Марс": 50.0})])
    assert [h["planet"] for h in w] == ["Венера", "Меркурий"]  # tightest first: Venus △ Anya's Sun (0.5°), Mercury ☌ Misha's Sun (1°)
    assert w[0]["glyph"] == "△" and w[0]["tone"] == "synergy" and w[1]["glyph"] == "☌" and w[1]["who"] == "Миша"
    assert all(h["orb"] <= ORB for h in w) and weather(sky, []) == []
    print("ok")
