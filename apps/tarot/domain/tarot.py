"""Arcana layer (ADR-0006): deterministic arcana per person and per pair; link rules in docs/methodology/tarot.md."""

from dataclasses import dataclass
from datetime import date

from apps.core.domain.scoring import Factor, ScoreResult, clamp

# (name, keyword, portrait) — our own wording, 1..22 (22 = Шут)
ARCANA = [
    ("Маг", "воля", "Превращает идеи в дела и любит начинать первым."),
    ("Верховная Жрица", "интуиция", "Чувствует больше, чем говорит, и доверяет внутреннему голосу."),
    ("Императрица", "забота", "Создаёт уют, щедра на тепло и внимание."),
    ("Император", "структура", "Строит опору, любит понятные правила и ответственность."),
    ("Иерофант", "ценности", "Опирается на традиции и важные для него принципы."),
    ("Влюблённые", "выбор", "Ищет союз по сердцу и честный выбор."),
    ("Колесница", "курс", "Держит руль, ставит цель и не любит сворачивать."),
    ("Сила", "мягкая сила", "Справляется терпением и теплом, а не напором."),
    ("Отшельник", "глубина", "Нуждается в тишине, чтобы понять главное."),
    ("Колесо Фортуны", "перемены", "Живёт циклами и легко меняет планы."),
    ("Справедливость", "баланс", "Ценит честность и ясные правила."),
    ("Повешенный", "новый взгляд", "Умеет остановиться и посмотреть под другим углом."),
    ("Смерть", "обновление", "Закрывает старое, чтобы освободить место новому."),
    ("Умеренность", "мера", "Ищет середину и умеет смешивать противоположности."),
    ("Дьявол", "страсть", "Живёт сильными желаниями и глубокой привязанностью."),
    ("Башня", "встряска", "Не терпит фальши и ломает то, что не работает."),
    ("Звезда", "надежда", "Вдохновляет и верит в лучшее даже после бурь."),
    ("Луна", "чувства", "Тонко чувствует, но иногда тонет в сомнениях."),
    ("Солнце", "радость", "Открыт, тёпл и заряжает энергией."),
    ("Суд", "переоценка", "Умеет честно пересмотреть и выбрать заново."),
    ("Мир", "целостность", "Стремится к завершённости и гармонии."),
    ("Шут", "свобода", "Спонтанен, лёгок на подъём и открыт новому."),
]
# Pair-arcana families (documented in docs/methodology/tarot.md)
UNITING = {1, 3, 6, 14, 17, 19, 21}
TESTING = {13, 15, 16, 18}


def reduce22(n: int) -> int:
    while n > 22:
        n -= 22
    return n or 22


def arcana_of(d: date) -> int:
    return reduce22(sum(int(c) for c in d.strftime("%d%m%Y")))


def pair_arcana(a: int, b: int) -> int:
    return reduce22(a + b)


@dataclass(frozen=True)
class Link:
    type: str
    tone: str
    score: int


def link(a: int, b: int) -> Link:
    p = pair_arcana(a, b)
    if a == b:
        return Link("Зеркальные", "neutral", 72)
    if p in UNITING:
        return Link("Дополняющие", "synergy", 86)
    if p in TESTING:
        return Link("Напряжённые", "attention", 55)
    return Link("Нейтральные", "neutral", 68)


def how(label_a: str, d_a: date, label_b: str, d_b: date) -> list[str]:
    def line(label: str, d: date) -> str:
        digits = [int(c) for c in d.strftime("%d%m%Y")]
        s = sum(digits)
        steps = f"{s}" + (f" → {s} − 22 = {s - 22}" if s > 22 else "") + (f" → {s - 44}" if s - 22 > 22 else "")
        return f"Дата {label} {d:%d.%m.%Y} → {'+'.join(map(str, digits))} = {steps} · {ARCANA[arcana_of(d) - 1][0]}"

    a, b = arcana_of(d_a), arcana_of(d_b)
    total = a + b
    pair = (
        f"Аркан пары: {a} + {b} = {total}"
        + (f" → {total} − 22 = {pair_arcana(a, b)}" if total > 22 else "")
        + f" · {ARCANA[pair_arcana(a, b) - 1][0]}"
    )
    return [line(label_a, d_a), line(label_b, d_b), pair]


def score(d_a: date, d_b: date) -> ScoreResult:
    a, b = arcana_of(d_a), arcana_of(d_b)
    lk = link(a, b)
    p = pair_arcana(a, b)
    factor = Factor(
        f"Арканы {a} и {b} → аркан пары {p}", f"{ARCANA[p - 1][0]} · связь: {lk.type.lower()}", (lk.score - 65) / 30, "symbolic"
    )
    passion = 84 if p in {6, 15, 19, 1} else 70
    return ScoreResult(clamp(lk.score), 95, [factor], {"passion": passion, "emotions": 78 if p in {2, 3, 17, 18} else 68})
