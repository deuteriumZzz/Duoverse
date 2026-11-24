"""«Близость 18+»: each partner privately marks wishes «да / может быть / нет»; the pair sees only what matches.
A «нет» is never shown, and neither is anything only one of you chose. Phrasing stays non-explicit on purpose.
"""

YES, MAYBE, NO = "yes", "maybe", "no"
CHOICES = {YES: "Да", MAYBE: "Может быть", NO: "Нет"}
THEMES: dict[str, list[tuple[str, str]]] = {
    "Нежность": [
        ("hug", "Долгие объятия без повода"),
        ("massage", "Массаж перед сном"),
        ("cuddle", "Засыпать в обнимку"),
        ("kiss", "Целоваться дольше обычного"),
    ],
    "Романтика": [
        ("surprise", "Свидание-сюрприз, которое полностью планирует один из вас"),
        ("candles", "Ужин при свечах дома"),
        ("note", "Неожиданный комплимент посреди дня"),
        ("dance", "Танец вдвоём дома"),
    ],
    "Игра": [
        ("flirt", "Флирт в переписке в течение дня"),
        ("role", "Ролевая игра с лёгким сценарием"),
        ("truth", "«Правда или действие» для двоих"),
        ("lead", "Договариваться, кто сегодня ведёт"),
    ],
    "Новизна": [
        ("place", "Близость в непривычном месте дома"),
        ("trip", "Спонтанная поездка с ночёвкой"),
        ("look", "Новый образ или наряд для партнёра"),
        ("fantasy", "Рассказать о фантазии словами"),
    ],
    "Разговор": [
        ("likes", "Обсудить, что нравится больше всего"),
        ("stop", "Договориться о стоп-слове для неловких моментов"),
        ("say", "Говорить, что приятно, прямо в моменте"),
        ("monthly", "Раз в месяц обсуждать, что хочется попробовать"),
    ],
}
TITLES = {key: title for items in THEMES.values() for key, title in items}


def clean(form: dict[str, str]) -> dict[str, str]:
    """Only known wishes and known answers; anything else is dropped."""
    return {k: v for k, v in form.items() if k in TITLES and v in CHOICES}


def matches(mine: dict[str, str], theirs: dict[str, str]) -> dict[str, list[str]]:
    """{"both": titles you both said «да» to, "talk": both at least «может быть» (not both «да»)}; nothing else leaks."""
    both, talk = [], []
    for key, title in TITLES.items():
        pair = {mine.get(key), theirs.get(key)}
        if pair == {YES}:
            both.append(title)
        elif pair <= {YES, MAYBE} and None not in pair:
            talk.append(title)
    return {"both": both, "talk": talk}


if __name__ == "__main__":
    a = {"hug": YES, "role": MAYBE, "trip": YES, "place": NO, "kiss": MAYBE}
    b = {"hug": YES, "role": YES, "trip": NO, "place": YES, "kiss": MAYBE, "bogus": YES}
    m = matches(a, clean(b))
    assert m == {"both": ["Долгие объятия без повода"], "talk": ["Целоваться дольше обычного", "Ролевая игра с лёгким сценарием"]}
    assert "bogus" not in clean(b) and clean({"hug": "sure"}) == {} and len(TITLES) == 20
    print("ok")
