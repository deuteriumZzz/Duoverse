"""Questionnaires (scientific layer). Methodology: docs/methodology/psychology.md.

Big Five — Mini-IPIP (Donnellan et al., 2006; IPIP items are public domain), our Russian translation.
Attachment and conflict — our own items for the anxiety/avoidance dimensions and Gottman's constructs
(proprietary inventories are not reproduced). All wording requires psychologist review before production.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    scale: str
    reverse: bool = False


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    hint: str
    items: tuple[Item, ...]


LIKERT = 5  # 1 «совсем не про меня» … 5 «точно про меня»

BIG_FIVE = Section(
    "big5",
    "Big Five",
    "Насколько это про вас?",
    (
        Item("e1", "Я — душа компании.", "E"),
        Item("a1", "Я сочувствую чувствам других.", "A"),
        Item("c1", "Я делаю дела сразу, не откладывая.", "C"),
        Item("n1", "У меня часто меняется настроение.", "N"),
        Item("o1", "У меня яркое воображение.", "O"),
        Item("e2", "Я немногословен(на).", "E", True),
        Item("a2", "Мне не очень интересны чужие проблемы.", "A", True),
        Item("c2", "Я часто забываю класть вещи на место.", "C", True),
        Item("n2", "Большую часть времени я спокоен(на).", "N", True),
        Item("o2", "Абстрактные идеи мне не интересны.", "O", True),
        Item("e3", "На вечеринках я общаюсь со множеством людей.", "E"),
        Item("a3", "Я чувствую эмоции других людей.", "A"),
        Item("c3", "Я люблю порядок.", "C"),
        Item("n3", "Меня легко расстроить.", "N"),
        Item("o3", "Мне трудно понимать абстрактные идеи.", "O", True),
        Item("e4", "Я предпочитаю держаться в тени.", "E", True),
        Item("a4", "Другие люди мне не особенно интересны.", "A", True),
        Item("c4", "Я часто устраиваю беспорядок.", "C", True),
        Item("n4", "Мне редко бывает грустно.", "N", True),
        Item("o4", "У меня не очень богатое воображение.", "O", True),
    ),
)

ATTACHMENT = Section(
    "attachment",
    "Привязанность",
    "Как вы чувствуете себя в близких отношениях?",
    (
        Item("anx1", "Я волнуюсь, что партнёр любит меня меньше, чем я его.", "anx"),
        Item("anx2", "Если партнёр долго не отвечает, я начинаю тревожиться.", "anx"),
        Item("anx3", "Мне нужно часто слышать, что я важен(на) партнёру.", "anx"),
        Item("anx4", "Я редко переживаю, что отношения закончатся.", "anx", True),
        Item("avo1", "Когда становится слишком близко, мне хочется отдалиться.", "avo"),
        Item("avo2", "Мне непросто рассказывать партнёру о своих чувствах.", "avo"),
        Item("avo3", "Я предпочитаю справляться с трудностями сам(а).", "avo"),
        Item("avo4", "Мне легко просить партнёра о поддержке.", "avo", True),
    ),
)

CONFLICT = Section(
    "conflict",
    "Конфликт",
    "Как обычно проходят ваши споры?",
    (
        Item("crit1", "В споре я говорю «ты всегда…» или «ты никогда…».", "criticism"),
        Item("crit2", "Я начинаю разговор о проблеме с того, что со мной не так, а не с упрёка.", "criticism", True),
        Item("cont1", "В ссоре я бываю саркастичен(на) или закатываю глаза.", "contempt"),
        Item("cont2", "Даже злясь, я отношусь к партнёру с уважением.", "contempt", True),
        Item("def1", "На замечание я сразу отвечаю встречной претензией.", "defensiveness"),
        Item("def2", "Я могу признать свою часть вины в ссоре.", "defensiveness", True),
        Item("ston1", "Когда спор накаляется, я замолкаю и закрываюсь.", "stonewalling"),
        Item("ston2", "Мне удаётся оставаться в разговоре, даже когда тяжело.", "stonewalling", True),
        Item("rep1", "После ссоры мы быстро находим способ помириться.", "repair"),
        Item("rep2", "Шутка или прикосновение помогают нам остановить ссору.", "repair"),
    ),
)

SECTIONS = (BIG_FIVE, ATTACHMENT, CONFLICT)
ITEMS = {i.id: i for s in SECTIONS for i in s.items}
