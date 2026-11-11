"""Builds the full Report from the four universes, the weighting engine and the knowledge base.

Numbers come from deterministic code; every sentence comes from a knowledge block (or a template over facts);
the optional LLM stitcher only rewrites the summary and sphere stories from these same blocks (prompt §4).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time
from typing import Protocol

from apps.astrology.application.ports import EphemerisProvider, Geocoder
from apps.astrology.domain import chart as astro_chart
from apps.astrology.domain import interpret
from apps.astrology.domain.chart import (
    POINTS,
    SPHERE_CATEGORY,
    BirthData,
    Chart,
    Place,
    balance,
    composite,
    sphere_effects,
    sphere_score,
)
from apps.compatibility.domain import engine
from apps.compatibility.domain.archetypes import ELEMENTS, MODES, dynamic_for, mode_from_life_path, pair_name, pair_tagline, role_for
from apps.compatibility.domain.report import (
    Accuracy,
    Arcana,
    Aspect,
    AstrologySection,
    Category,
    ChartBalance,
    CompositePos,
    Daily,
    Evidence,
    GottmanItem,
    Habit,
    Insight,
    Level,
    MatrixPoint,
    NumberPair,
    NumerologySection,
    OceanTrait,
    Overlay,
    PairType,
    Partner,
    PlanetPos,
    PsychologySection,
    Report,
    Risk,
    Sphere,
    SphereFactor,
    TarotSection,
    Tone,
    Universe,
    UniverseKey,
)
from apps.compatibility.domain.report import Layer as EvidenceLayer
from apps.core.domain.names import forms, gen
from apps.core.domain.scoring import Factor, ScoreResult, clamp
from apps.numerology.domain import numerology as num
from apps.psychology.domain import scoring as psy
from apps.tarot.domain import tarot

CATEGORIES = {
    "passion": ("Страсть", "flame"),
    "emotions": ("Эмоции", "heart"),
    "communication": ("Коммуникация", "message-circle"),
    "values": ("Ценности", "gem"),
    "conflict": ("Конфликт и восстановление", "shield-check"),
    "home": ("Быт", "house"),
}
SPHERES = ["attraction", "sex", "emotions", "talk", "conflicts", "trust", "power", "shadows", "home", "money", "plans", "people", "growth"]
TENSE_SPHERES = {"sex", "emotions", "talk", "conflicts", "trust", "power", "shadows"}
# which spheres each non-astrological factor speaks to
CATEGORY_SPHERES = {
    "emotions": ["emotions", "trust"],
    "conflict": ["conflicts", "shadows", "power"],
    "communication": ["talk", "people"],
    "home": ["home"],
    "values": ["plans", "money"],
    "passion": ["attraction", "sex"],
}
SOURCE_SPHERES = {
    "Привязанность": ["emotions", "trust", "shadows"],
    "Эмоциональная чувствительность": ["shadows", "emotions"],
    "Презрение": ["conflicts", "shadows"],
    "Уход в себя": ["conflicts", "talk"],
    "Индекс восстановления": ["conflicts"],
}
UNIVERSES: dict[UniverseKey, tuple[str, str, EvidenceLayer]] = {
    "astrology": ("Астрология", "orbit", "symbolic"),
    "psychology": ("Психология", "brain", "scientific"),
    "numerology": ("Числа", "hash", "symbolic"),
    "tarot": ("Таро", "layers", "symbolic"),
}
TRAIT_NOTE = {
    "O": ("Обоим нравится новое — хорошая почва для совместных приключений.", "Одному нужно новое, другому — проверенное: чередуйте."),
    "C": (
        "Похожее отношение к порядку и планам — меньше бытовых трений.",
        "Один держит структуру — важно, чтобы это не превращалось в контроль.",
    ),
    "E": ("Похожая потребность в людях — легко планировать досуг.", "Разный «заряд» от людей: договоритесь о тихих вечерах и выходах."),
    "A": ("Оба склонны уступать и заботиться — сильная сторона пары.", "Одному уступать сложнее — не принимайте это лично."),
    "N": ("Похожая реакция на стресс — вы понимаете тревоги друг друга.", "Один острее переживает стресс, другой — стабилизатор."),
}
LEVELS: dict[str, int] = {"low": 0, "mid": 1, "high": 2}


class Knowledge(Protocol):
    used: list[str]

    def series(self, prefix: str) -> list[dict]: ...

    def text(self, key: str, default: str = "", **fmt: object) -> str: ...

    def data(self, key: str) -> dict: ...


class Stitcher(Protocol):
    def stitch(self, report: Report) -> Report: ...


@dataclass(frozen=True)
class PersonInput:
    id: str
    name: str
    birth_date: date
    birth_time: time | None = None
    birth_place: str | None = None
    answers: dict[str, int] | None = None
    birth_coords: tuple[float, float, str] | None = None  # lat, lon, IANA zone of a place picked on the map


@dataclass
class Deps:
    ephemeris: EphemerisProvider
    geocoder: Geocoder
    kb: Knowledge
    today: Callable[[], date] = date.today
    stitcher: Stitcher | None = None
    algorithm_version: str = "0.3.0"


def tone_of(score: int) -> Tone:
    return "synergy" if score >= 75 else "neutral" if score >= 60 else "attention" if score >= 45 else "risk"


def ev(f: Factor) -> Evidence:
    return Evidence(source=f.source, detail=f.detail, weight=round(f.weight, 2), layer=f.layer)


def arcana(n: int) -> Arcana:
    name, keyword, portrait = tarot.ARCANA[n - 1]
    return Arcana(number=n, name=name, keyword=keyword, portrait=portrait)


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def build_report(report_id: str, a: PersonInput, b: PersonInput, deps: Deps) -> Report:
    kb, today = deps.kb, deps.today()
    names = {f"a{k}": v for k, v in forms(a.name).items()} | {f"b{k}": v for k, v in forms(b.name).items()}  # {a}, {b_gen}, {a_ins}…

    # ── charts and universes ────────────────────────────────────────────────
    def place_of(p: PersonInput) -> Place | None:
        if p.birth_coords:
            return Place(p.birth_place or "", *p.birth_coords)
        return deps.geocoder.lookup(p.birth_place) if p.birth_place else None

    def chart_of(p: PersonInput) -> Chart:
        place = place_of(p)
        return deps.ephemeris.chart(BirthData(p.birth_date, p.birth_time if place else None, place))

    ca, cb = chart_of(a), chart_of(b)
    hits = astro_chart.synastry(ca, cb)
    overlay = astro_chart.houses_overlay(ca, cb, a.name, b.name) if ca.houses and cb.houses else None
    astro = astro_chart.score(ca, cb, hits, overlay)

    pa, pb = num.profile(a.birth_date, a.name, today), num.profile(b.birth_date, b.name, today)
    raw_numer = num.score(pa, pb)
    numer = ScoreResult(
        raw_numer.score,
        raw_numer.confidence,
        [Factor(f.source, f.detail, f.weight, f.layer, "values") for f in raw_numer.factors],
        {"values": raw_numer.score, "communication": raw_numer.score},
    )
    arc = tarot.score(a.birth_date, b.birth_date)

    psa = psy.profile(a.answers) if a.answers else None
    psb = psy.profile(b.answers) if b.answers else None
    psych = psy.score(psa, psb) if psa and psb else None

    results: dict[str, ScoreResult | None] = {"astrology": astro, "psychology": psych, "numerology": numer, "tarot": arc}
    combined = engine.combine(results)
    factors = [f for r in results.values() if r for f in r.factors]

    # ── categories: weighted by the (redistributed) universe weights ────────
    categories: list[Category] = []
    cat_scores: dict[str, int] = {}
    for key, (title, icon) in CATEGORIES.items():
        parts = [(r.categories[key], combined.weights[u]) for u, r in results.items() if r and key in r.categories and combined.weights[u]]
        score = clamp(sum(s * w for s, w in parts) / sum(w for _, w in parts)) if parts else combined.total
        cat_scores[key] = score
        evidence = sorted((f for f in factors if f.category == key), key=lambda f: -abs(f.weight))[:3] or factors[:1]
        categories.append(
            Category(
                key=key,
                title=title,
                icon=icon,
                score=score,
                tone=tone_of(score),
                verdict=kb.text(f"CAT:{key}:{tone_of(score)}"),
                evidence=[ev(f) for f in evidence],
            )
        )
    ranked = sorted(cat_scores, key=lambda k: -cat_scores[k])
    strong, weak = ranked[:2], ranked[::-1][:2]

    def insight(cat: str, kind: str) -> Insight:
        d = kb.data(f"INSIGHT:{cat}:{kind}")
        evidence = sorted((f for f in factors if f.category == cat and (f.weight > 0) == (kind == "good")), key=lambda f: -abs(f.weight))[
            :2
        ]
        tone: Tone = "synergy" if kind == "good" else ("risk" if cat_scores[cat] < 45 else "attention")
        return Insight(
            title=d.get("title", CATEGORIES[cat][0]), text=d.get("text", "").format(**names), tone=tone, evidence=[ev(f) for f in evidence]
        )

    # ── roles and pair type ────────────────────────────────────────────────
    ra = role_for(astro_chart.dominant_element(ca), mode_from_life_path(pa.life_path))
    rb = role_for(astro_chart.dominant_element(cb), mode_from_life_path(pb.life_path))
    dyn = dynamic_for(ra, rb)

    def role_why(c: Chart, life_path: int, element: str, mode: str, prof: psy.PsychProfile | None) -> list[Evidence]:
        counts = astro_chart.element_counts(c)
        out = [
            Evidence(
                source=f"Стихия: {ELEMENTS[element]}",
                detail=f"{counts[element]} из 5 личных планет · "
                + ", ".join(f"{p} в {c.sign(p)}" for p in ("Солнце", "Луна", "Венера", "Марс")),
                weight=0.8,
                layer="symbolic",
            ),
            Evidence(source=f"Число пути {life_path}", detail=f"режим: {MODES[mode]}", weight=0.5, layer="symbolic"),
        ]
        if prof:
            out.append(
                Evidence(
                    source=f"Открытость {prof.ocean['O']} · добросовестность {prof.ocean['C']}",
                    detail="психологический профиль дополняет роль",
                    weight=0.3,
                    layer="scientific",
                )
            )
        return out

    pair_key = f"PAIRTYPE:{min(ra.key, rb.key)}+{max(ra.key, rb.key)}"
    description = kb.text(pair_key) or f"{kb.text(f'ROLE:{ra.key}')} {kb.text(f'ROLE:{rb.key}')}"
    pair_type = PairType(
        name=pair_name(ra, rb),
        role_a=ra.key,
        role_b=rb.key,
        dynamic=dyn.key,
        icon="sparkles",
        tagline=pair_tagline(ra, rb, a.name, b.name),
        description=description.strip(),
        traits=[CATEGORIES[strong[0]][0], CATEGORIES[strong[1]][0], f"Договориться: {CATEGORIES[weak[0]][0].lower()}"],
        why_a=role_why(ca, pa.life_path, ra.element, ra.mode, psa),
        why_b=role_why(cb, pb.life_path, rb.element, rb.mode, psb),
    )

    # ── sections ───────────────────────────────────────────────────────────
    top = hits[0] if hits else None

    def kb_text(key: str, default: str, **extra: str) -> str:
        """Reviewed block for `key` if there is one, else our generated text. Blocks may use {a}, {b_gen}, {owner_dat}…"""
        return kb.text(key, default.replace("{", "(").replace("}", ")"), **names, **extra)

    def person_names(prefix: str, name: str) -> dict[str, str]:
        return {f"{prefix}{k}": v for k, v in forms(name).items()}

    def planet_rows(c: Chart, name: str) -> list[PlanetPos]:
        return [
            PlanetPos(
                name=p,
                lon=c.planets[p],
                glyph=POINTS[p].glyph,
                sign=c.sign(p),
                degree=c.degree(p),
                house=c.house(p),
                retro=c.retro(p),
                dignity=c.dignity(p),
                text=kb_text(
                    f"PLACEMENT:{p}:{c.sign(p)}",
                    interpret.placement_text(name, p, c.sign(p), c.house(p), c.retro(p), c.dignity(p)),
                    **person_names("name", name),
                ),
            )
            for p in c.points
        ]

    def aspect_row(h) -> Aspect:
        return Aspect(
            planet_a=h.planet_a,
            symbol=h.kind.symbol,
            aspect=h.kind.name,
            planet_b=h.planet_b,
            orb=h.orb,
            tone=tone_of(65 + round(h.effect * 3)),
            meaning=h.meaning,
            key=h.key,
            major=h.kind.major,
            double=h.double,
            spheres=list(h.spheres),
            text=kb_text(f"ASPECT:{h.key}", interpret.aspect_text(h, a.name, b.name)),
        )

    names_by_side = {"a": (a.name, b.name), "b": (b.name, a.name)}
    overlays = [
        Overlay(
            planet=o.planet,
            owner=o.owner,
            house=o.house,
            tone=tone_of(65 + round(o.effect * 4)),  # type: ignore[arg-type]
            text=kb_text(
                f"OVERLAY:{o.key}",
                interpret.overlay_text(o, *names_by_side[o.owner]),
                **person_names("owner", names_by_side[o.owner][0]),
                **person_names("other", names_by_side[o.owner][1]),
            ),
        )
        for o in (overlay.hits if overlay else [])
    ]
    comp = composite(ca, cb)
    major_hits = [h for h in hits if h.kind.major]
    astrology = AstrologySection(
        houses_available=bool(ca.houses and cb.houses),
        planets_a=planet_rows(ca, a.name),
        planets_b=planet_rows(cb, b.name),
        houses_a=ca.houses or [],
        summary=(
            f"Солнце {gen(a.name)} в знаке {ca.sign('Солнце')}, у {gen(b.name)} — в знаке {cb.sign('Солнце')}; Луна — {ca.sign('Луна')} и {cb.sign('Луна')}. "
            f"Между картами {len(major_hits)} мажорных и {len(hits) - len(major_hits)} минорных аспектов, двойных связей — {sum(h.double for h in hits)}"
            + (f"; самый сильный — {top.planet_a} {top.kind.name} {top.planet_b} (орб {top.orb}°)." if top else ".")
            + (
                ""
                if ca.exact_time and cb.exact_time
                else " Без точного времени рождения дома, Асцендент и наложения не считаются, Луна — приблизительно."
            )
        ),
        aspects=[aspect_row(h) for h in major_hits[:9]],
        all_aspects=[aspect_row(h) for h in hits],
        overlays=overlays,
        composite=[
            CompositePos(
                point=p,
                sign=comp.sign(p),
                house=comp.house(p),
                text=kb_text(f"COMPOSITE:{p}:{comp.sign(p)}", interpret.composite_text(p, comp.sign(p), comp.house(p))),
            )
            for p in ["Солнце", "Луна", "Меркурий", "Венера", "Марс", "Юпитер", "Сатурн", "Асцендент"]
            if p in comp.planets
        ],
        composite_aspects=[f"{p} {k.symbol} {q} — {k.name}, орб {orb}°" for p, q, k, orb in comp.aspects[:10]],
        balance_a=ChartBalance(**balance(ca).__dict__),
        balance_b=ChartBalance(**balance(cb).__dict__),
        insights=[
            Insight(title=f.source, text=f"{_cap(f.detail)} — это добавляет паре узнавания и тепла.", tone="synergy", evidence=[ev(f)])
            for f in (overlay.lines if overlay else [])
            if f.weight > 0
        ][:4],
    )

    if psa and psb and psych:
        styles = {psa.attachment.split(",")[0], psb.attachment.split(",")[0]}
        att_key = (
            "secure"
            if psa.secure and psb.secure
            else "pursue"
            if styles == {"Тревожный", "Избегающий"}
            else "mixed"
            if (psa.secure or psb.secure)
            else "insecure"
        )
        gottman = []
        for h, title in psy.HORSEMEN.items():
            worst: Level = max(psa.horsemen[h], psb.horsemen[h], key=lambda lv: LEVELS[lv])  # type: ignore[assignment,arg-type]
            gottman.append(
                GottmanItem(
                    key=h,
                    title=title,
                    level=worst,
                    note="Почти не встречается — хороший знак." if worst == "low" else kb.text(f"PSY:horseman:{h}"),
                )
            )
        psychology = PsychologySection(
            available=True,
            ocean=[
                OceanTrait(
                    key=t, title=psy.TRAITS[t], a=psa.ocean[t], b=psb.ocean[t], note=TRAIT_NOTE[t][abs(psa.ocean[t] - psb.ocean[t]) >= 25]
                )
                for t in ("O", "C", "E", "A", "N")
            ],
            attachment_a=psa.attachment,
            attachment_b=psb.attachment,
            attachment_note=kb.text(f"PSY:attachment:{att_key}"),
            gottman=gottman,
            repair_index=round((psa.repair + psb.repair) / 2),
            insights=[
                Insight(title=f.source, text=f"{_cap(f.detail)}.", tone="synergy" if f.weight > 0 else "attention", evidence=[ev(f)])
                for f in sorted(psych.factors, key=lambda f: f.weight)[:2]
            ],
        )
    else:
        psychology = PsychologySection(available=False)

    rel = num.relation(pa.life_path, pb.life_path)
    numbers = [
        NumberPair(
            title="Число жизненного пути",
            a=pa.life_path,
            b=pb.life_path,
            tone=tone_of(rel[0]),
            meaning=f"{pa.life_path} — {num.KEYWORDS[pa.life_path]}; {pb.life_path} — {num.KEYWORDS[pb.life_path]}. {_cap(rel[1])}.",
        )
    ]
    if pa.destiny and pb.destiny:
        rd = num.relation(pa.destiny, pb.destiny)
        numbers.append(
            NumberPair(
                title="Число судьбы",
                a=pa.destiny,
                b=pb.destiny,
                tone=tone_of(rd[0]),
                meaning=f"По имени: {num.KEYWORDS[pa.destiny]} и {num.KEYWORDS[pb.destiny]}. {_cap(rd[1])}.",
            )
        )
    py_f = numer.factors[-1]
    numbers.append(
        NumberPair(
            title="Личный год",
            a=pa.personal_year,
            b=pb.personal_year,
            tone=tone_of(round(py_f.weight * 30 + 65)),
            meaning=_cap(py_f.detail) + ".",
        )
    )
    pair_n = num.pair_number(pa, pb)
    rel_a, rel_b = pa.matrix["Отношения"], pb.matrix["Отношения"]
    numerology = NumerologySection(
        numbers=numbers,
        pair_number=pair_n,
        pair_meaning=f"Число пары {pair_n} — {num.KEYWORDS[pair_n]}: вы сильнее всего, когда это общая тема.",
        matrix=[MatrixPoint(title=k, a=pa.matrix[k], b=pb.matrix[k]) for k in pa.matrix],
        insights=[
            Insight(
                title="Точка «Отношения» в Матрице",
                tone="neutral",
                text=f"У {gen(a.name)} — {tarot.ARCANA[rel_a - 1][0]} ({tarot.ARCANA[rel_a - 1][1]}), у {gen(b.name)} — {tarot.ARCANA[rel_b - 1][0]} ({tarot.ARCANA[rel_b - 1][1]}). Так каждый из вас понимает близость — об этом стоит поговорить вслух.",
                evidence=[Evidence(source="Матрица судьбы", detail=f"точка «Отношения»: {rel_a} и {rel_b}", weight=0.0, layer="symbolic")],
            )
        ],
    )

    a_arc, b_arc = tarot.arcana_of(a.birth_date), tarot.arcana_of(b.birth_date)
    p_arc, lk = tarot.pair_arcana(a_arc, b_arc), tarot.link(a_arc, b_arc)
    portrait_pair = tarot.ARCANA[p_arc - 1][2]
    tarot_section = TarotSection(
        a=arcana(a_arc),
        b=arcana(b_arc),
        pair=arcana(p_arc),
        link_type=lk.type,
        link_tone=lk.tone,  # type: ignore[arg-type]
        reading=kb.text(f"TAROT:pair:{min(a_arc, b_arc)}+{max(a_arc, b_arc)}")
        or f"{tarot.ARCANA[a_arc - 1][2]} {tarot.ARCANA[b_arc - 1][2]} Вместе это {tarot.ARCANA[p_arc - 1][0]}: {portrait_pair[:1].lower()}{portrait_pair[1:]}",
        questions=[kb.data(f"SPHERE:{s}").get("question", "") for s in ("plans", "talk", "growth")],
        how=tarot.how(a.name, a.birth_date, b.name, b.birth_date),
    )

    # ── universes, accuracy ────────────────────────────────────────────────
    exact = {p.name: bool(p.birth_time and place_of(p)) for p in (a, b)}
    accuracy, missing = 46, []
    for p in (a, b):
        if exact[p.name]:
            accuracy += 14
        else:
            missing.append(f"Время или место рождения {gen(p.name)} не указаны — дома и Асцендент не считаются")
    if psych:
        accuracy += 20
    else:
        missing.append("Психологические анкеты пройдены не обоими — научный слой не учтён")
    verdicts = {
        "astrology": f"{interpret.aspect_title(top, a.name, b.name)} — самая сильная связь ваших карт."
        if top
        else "Тесных аспектов немного — связь держится на других слоях",
        "psychology": f"{psa.attachment} · {psb.attachment}, восстановление {psychology.repair_index}"
        if psa and psb
        else "Пройдите анкеты, чтобы включить научный слой",
        "numerology": f"{pa.life_path} и {pb.life_path}: {num.KEYWORDS[pa.life_path]} встречает {num.KEYWORDS[pb.life_path]}",
        "tarot": f"{tarot.ARCANA[a_arc - 1][0]} и {tarot.ARCANA[b_arc - 1][0]} дают аркан пары — {tarot.ARCANA[p_arc - 1][0]}",
    }
    universes = []
    for key, (title, icon, layer) in UNIVERSES.items():
        r = results[key]
        miss = (
            "Анкеты не пройдены"
            if key == "psychology" and not r
            else "Нет точного времени или места рождения"
            if key == "astrology" and not all(exact.values())
            else None
        )
        universes.append(
            Universe(
                key=key,
                title=title,
                icon=icon,
                layer=layer,
                score=r.score if r else None,
                confidence=r.confidence if r else 0,
                weight=combined.weights[key],
                verdict=verdicts[key],
                missing=miss,
            )
        )  # type: ignore[arg-type]

    # ── risks, habits, daily, spheres ──────────────────────────────────────
    risks = []
    for cat in [c for c in reversed(ranked) if cat_scores[c] < 72][:4]:
        d = kb.data(f"RISK:{cat}")
        s = cat_scores[cat]
        likelihood: Level = "high" if s < 50 else "mid" if s < 62 else "low"
        impact: Level = "high" if cat in ("conflict", "emotions") else "mid" if cat in ("values", "communication") else "low"
        risks.append(
            Risk(
                title=d.get("title", CATEGORIES[cat][0]),
                likelihood=likelihood,
                impact=impact,
                note=d.get("note", ""),
                mitigation=d.get("mitigation", ""),
            )
        )
    habits = []
    for cat in list(reversed(ranked))[:5]:
        d = kb.data(f"HABIT:{cat}")
        if d:
            f = next((x for x in sorted(factors, key=lambda x: x.weight) if x.category == cat), factors[0])
            habits.append(Habit(title=d["title"], cadence=d["cadence"], duration=d["duration"], why=d["why"], evidence=ev(f)))
    daily_d = kb.data(f"DAILY:{weak[0]}")
    daily = Daily(question=daily_d.get("question", ""), habit=daily_d.get("habit", ""), streak=0, week=[False] * 7)

    astro_sphere = sphere_effects(hits, overlay)
    other: dict[str, list[tuple[Factor, str]]] = {k: [] for k in SPHERES}
    for f in psych.factors if psych else []:
        for sp in SOURCE_SPHERES.get(f.source, CATEGORY_SPHERES.get(f.category or "", [])):
            other[sp].append((f, "psychology"))
    for f in arc.factors:
        for sp in ("attraction", "growth"):
            other[sp].append((f, "tarot"))
    for f in numer.factors[:1]:
        for sp in ("plans", "talk", "money"):
            other[sp].append((f, "numerology"))

    spheres = []
    for key in SPHERES:
        d = kb.data(f"SPHERE:{key}")
        if not d:
            continue
        cat = SPHERE_CATEGORY[key]
        parts = [(sphere_score(astro_sphere[key]) or astro.categories[cat], combined.weights["astrology"])]
        if psych:
            parts.append((psych.categories[cat], combined.weights["psychology"]))
        if key in ("attraction", "growth", "sex", "emotions"):
            parts.append((arc.categories.get(cat, arc.score), combined.weights["tarot"]))
        if key in ("plans", "talk", "money"):
            parts.append((numer.score, combined.weights["numerology"]))
        score = clamp(sum(v * w for v, w in parts) / (sum(w for _, w in parts) or 1))

        sphere_hits = sorted([h for h in hits if key in h.spheres], key=lambda h: -abs(h.effect))[:4]
        sphere_overlays = sorted(
            [
                o
                for o in (overlay.hits if overlay else [])
                if key in o.spheres and POINTS[o.planet].kind in ("luminary", "personal", "outer")
            ],
            key=lambda o: -abs(o.effect),
        )[:2]
        items = [
            SphereFactor(
                title=interpret.aspect_title(h, a.name, b.name),
                text=kb_text(f"ASPECT:{h.key}", interpret.aspect_text(h, a.name, b.name)),
                tone=tone_of(65 + round(h.effect * 3)),
                layer="symbolic",
                universe="astrology",
                tech=f"{h.planet_a} {h.kind.symbol} {h.planet_b} · {h.kind.name}, орб {h.orb}°",
                ref=f"asp-{h.key}",
            )
            for h in sphere_hits
        ]
        items += [
            SphereFactor(
                title=interpret.overlay_title(o, *names_by_side[o.owner]),
                text=kb_text(
                    f"OVERLAY:{o.key}",
                    interpret.overlay_text(o, *names_by_side[o.owner]),
                    **person_names("owner", names_by_side[o.owner][0]),
                    **person_names("other", names_by_side[o.owner][1]),
                ),
                tone=tone_of(65 + round(o.effect * 4)),
                layer="symbolic",
                universe="astrology",
                tech=f"{o.planet} в {o.house}-м доме",
                ref=f"ov-{o.owner}-{o.key}",
            )
            for o in sphere_overlays
        ]
        items += [
            SphereFactor(title=f.source, text=f"{_cap(f.detail)}.", tone=tone_of(65 + round(f.weight * 30)), layer=f.layer, universe=u)  # type: ignore[arg-type]
            for f, u in other[key][:3]
        ]
        tense = [
            h for h in hits if key in h.spheres and h.effect < -2 and h.planet_a in interpret.PLANET and h.planet_b in interpret.PLANET
        ]
        evidence = sorted((f for f in factors if f.category == cat), key=lambda f: -abs(f.weight))[:3]
        spheres.append(
            Sphere(
                key=key,
                title=d["title"],
                icon=d["icon"],
                score=score,
                tone=tone_of(score),
                summary=kb.text(f"CAT:{d['cats'][0]}:{tone_of(score)}"),
                story=[d["intro"].format(**names), d["strong"] if score >= 75 else d["weak"]],  # one honest reading per sphere
                evidence=[ev(f) for f in evidence],
                actions=[d["do"]],
                question=d["question"],
                factors=items,
                script=interpret.conflict_script(min(tense, key=lambda h: h.effect), a.name, b.name)
                if key in TENSE_SPHERES and tense
                else None,
                exercise=_exercise(kb.series(f"EXERCISE:{key}:"), d.get("exercise", "")),
                adult=bool(d.get("adult")),
            )
        )

    # habits grow out of the weakest spheres: two per sphere, each tied to that sphere's strongest reason
    sphere_habits = []
    for weak_sphere in sorted(spheres, key=lambda x: x.score)[:3]:
        reason = weak_sphere.evidence[0] if weak_sphere.evidence else ev(factors[0])
        for hb in kb.series(f"HABIT:{weak_sphere.key}:")[:2]:
            sphere_habits.append(Habit(title=hb["title"], cadence=hb["cadence"], duration=hb["duration"], why=hb["why"], evidence=reason))
    habits = sphere_habits or habits

    report = Report(
        id=report_id,
        scenario="real",
        algorithm_version=deps.algorithm_version,
        created_at=today,
        partners=(
            Partner(
                id=a.id,
                name=a.name,
                side="a",
                birth_date=a.birth_date,
                birth_time=a.birth_time,
                birth_place=a.birth_place,
                sun_sign=ca.sign("Солнце"),
                has_psych=bool(a.answers),
            ),
            Partner(
                id=b.id,
                name=b.name,
                side="b",
                birth_date=b.birth_date,
                birth_time=b.birth_time,
                birth_place=b.birth_place,
                sun_sign=cb.sign("Солнце"),
                has_psych=bool(b.answers),
            ),
        ),
        total_score=combined.total,
        agreement_index=combined.agreement,
        agreement_note=(
            "Все вселенные видят пару похоже — выводам можно доверять больше."
            if combined.agreement >= 75
            else f"Вселенные расходятся: сильнее всего у вас «{CATEGORIES[strong[0]][0].lower()}», слабее — «{CATEGORIES[weak[0]][0].lower()}». Научный слой смотрите отдельно."
        ),
        summary=kb.text(
            f"SUMMARY:{dyn.key}", a=a.name, b=b.name, strong=CATEGORIES[strong[0]][0].lower(), weak=CATEGORIES[weak[0]][0].lower()
        ),
        pair_type=pair_type,
        accuracy=Accuracy(value=min(accuracy, 96), missing=missing),
        universes=universes,
        categories=categories,
        synergy=[insight(c, "good") for c in strong],
        friction=[insight(c, "hard") for c in weak],
        risks=risks,
        astrology=astrology,
        psychology=psychology,
        numerology=numerology,
        tarot=tarot_section,
        habits=habits,
        daily=daily,
        spheres=spheres,
        depth={"dates": True, "time_place_a": exact[a.name], "time_place_b": exact[b.name], "psych": bool(psych)},
    )
    report = deps.stitcher.stitch(report) if deps.stitcher else report
    return report.model_copy(update={"kb_keys": sorted(set(kb.used))})


def _exercise(items: list[dict], fallback: str) -> str:
    """First exercise for the sphere from the knowledge base, as one readable paragraph."""
    if not items:
        return fallback
    e = items[0]
    steps = " ".join(f"{i}) {step}" for i, step in enumerate(e.get("steps", []), 1))
    return f"{e['title']} ({e.get('minutes', 10)} мин). {steps}".strip()
