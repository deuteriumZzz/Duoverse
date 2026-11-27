"""Questionnaires (scientific layer). Methodology: docs/methodology/psychology.md.

Big Five — the 50-item IPIP Big-Five Factor Markers (Goldberg, 1992; public domain, ipip.ori.org), our Russian
translation; ten items a trait instead of the four of Mini-IPIP (whose 20 items are among them and keep their ids e1…o4).
Attachment and conflict — our own items for the anxiety/avoidance dimensions and Gottman's constructs
(proprietary inventories are not reproduced). All wording requires psychologist review before production.
Reports saved with fewer answers still score: a scale is the mean of the items answered (scoring._scale).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    scale: str
    reverse: bool = False
    scene: str = ""  # the questionnaire picture to show (quiz_scenes.html), when it borrows a sibling item's one


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    hint: str
    items: tuple[Item, ...]


LIKERT = 5  # 1 «совсем не про меня» … 5 «точно про меня»

BIG_FIVE = Section(
    "big5",
    "Большая пятёрка",
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
        # the other thirty markers of IPIP-50, in the same E-A-C-N-O round; each borrows the scene of its nearest sibling
        Item("e5", "Мне легко и спокойно среди людей.", "E", scene="e3"),
        Item("a5", "Меня мало заботит, что чувствуют другие.", "A", True, scene="a2"),
        Item("c5", "Я ко всему готовлюсь заранее.", "C", scene="c1"),
        Item("n5", "Я легко поддаюсь стрессу.", "N", scene="n3"),
        Item("o5", "У меня богатый словарный запас.", "O", scene="o3"),
        Item("e6", "Обычно я первым(ой) начинаю разговор.", "E", scene="e1"),
        Item("a6", "Мне интересны люди.", "A", scene="a4"),
        Item("c6", "Я оставляю свои вещи где попало.", "C", True, scene="c2"),
        Item("n6", "Я часто о чём-то тревожусь.", "N", scene="n3"),
        Item("o6", "У меня бывают отличные идеи.", "O", scene="o1"),
        Item("e7", "Мне обычно особо нечего сказать.", "E", True, scene="e2"),
        Item("a7", "Бывает, я задеваю людей обидными словами.", "A", True, scene="a2"),
        Item("c7", "Я обращаю внимание на детали.", "C", scene="c3"),
        Item("n7", "Меня легко выбить из колеи.", "N", scene="n3"),
        Item("o7", "Я быстро схватываю новое.", "O", scene="o3"),
        Item("e8", "Не люблю привлекать к себе внимание.", "E", True, scene="e4"),
        Item("a8", "У меня мягкое сердце.", "A", scene="a1"),
        Item("c8", "Я увиливаю от своих обязанностей.", "C", True, scene="c1"),
        Item("n8", "Моё настроение то и дело меняется.", "N", scene="n1"),
        Item("o8", "Я употребляю сложные слова.", "O", scene="o3"),
        Item("e9", "Я не против быть в центре внимания.", "E", scene="e1"),
        Item("a9", "Я нахожу время для других.", "A", scene="a3"),
        Item("c9", "Я живу по расписанию.", "C", scene="c3"),
        Item("n9", "Меня легко вывести из себя.", "N", scene="n1"),
        Item("o9", "Я люблю поразмышлять о разном.", "O", scene="o2"),
        Item("e10", "С незнакомыми людьми я обычно молчу.", "E", True, scene="e2"),
        Item("a10", "Рядом со мной людям легко.", "A", scene="a1"),
        Item("c10", "В работе я требую от себя точности.", "C", scene="c3"),
        Item("n10", "Мне часто бывает грустно.", "N", scene="n4"),
        Item("o10", "У меня полно идей.", "O", scene="o1"),
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
        # four more each way, keyed both ways like the first eight, so a habit of agreeing doesn't tilt the result
        Item("anx5", "Я боюсь, что партнёр может разлюбить меня.", "anx", scene="anx1"),
        Item("avo5", "Мне неуютно, когда партнёр слишком во мне нуждается.", "avo", scene="avo1"),
        Item("anx6", "Если партнёр отдаляется, я думаю, что сделал(а) что-то не так.", "anx", scene="anx2"),
        Item("avo6", "Даже в близких отношениях мне важно сохранять дистанцию.", "avo", scene="avo1"),
        Item("anx7", "Я уверен(а), что нужен(на) партнёру по-настоящему.", "anx", True, scene="anx4"),
        Item("avo7", "Мне приятно делиться с партнёром самым личным.", "avo", True, scene="avo4"),
        Item("anx8", "Мне трудно успокоиться, пока мы не помиримся после ссоры.", "anx", scene="anx3"),
        Item("avo8", "Мне спокойнее, когда я ни от кого не завишу.", "avo", scene="avo3"),
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
