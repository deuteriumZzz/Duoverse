"""ReportProvider backed by the real engine. Demo scenarios use demo inputs; stored pairs go through the same builder."""

from collections.abc import Callable
from datetime import date
from typing import Any

from django.conf import settings

from apps.astrology.application.ports import EphemerisProvider, Geocoder
from apps.astrology.domain import chart as astro_chart
from apps.astrology.domain.chart import BirthData, Chart
from apps.compatibility.application.build_report import Deps, PersonInput, Stitcher, arcana, build_report, tone_of
from apps.compatibility.domain import engine
from apps.compatibility.domain.archetypes import ELEMENTS, MODES, Role, dynamic_for, mode_from_life_path, pair_name, pair_tagline, role_for
from apps.compatibility.domain.report import GenerationStep, QuickCategory, QuickResult, Report, ReportUnavailable, Scenario
from apps.core.domain.scoring import clamp
from apps.numerology.domain import numerology as num
from apps.tarot.domain import tarot

from .demo import SCENARIOS, demo_pair

STEPS = [
    GenerationStep(title="Строим натальные карты", detail="Swiss Ephemeris · 2 карты · 14 точек", icon="orbit"),
    GenerationStep(title="Считаем аспекты между картами", detail="5 видов аспектов, орбы до 8°", icon="sparkles"),
    GenerationStep(title="Числа и Матрица судьбы", detail="путь, судьба, личный год, 5 точек матрицы", icon="hash"),
    GenerationStep(title="Арканы партнёров и пары", detail="редукция дат → 22 Старших аркана", icon="layers"),
    GenerationStep(title="Психологический профиль", detail="Big Five, привязанность, индикаторы Готтмана", icon="brain"),
    GenerationStep(title="Сводим вселенные", detail="веса 35 / 35 / 15 / 15 · индекс согласия", icon="scale"),
    GenerationStep(title="Подбираем блоки знаний", detail="проверенные тексты по ключам расчёта", icon="book-open"),
    GenerationStep(title="Собираем текст и сверяем факты", detail="каждое утверждение — со ссылкой на расчёт", icon="shield-check"),
]


class EngineReportProvider:
    def __init__(
        self,
        ephemeris: EphemerisProvider,
        geocoder: Geocoder,
        knowledge: Callable[[], Any],
        stitcher: Callable[[], Stitcher | None] = lambda: None,
        today: Callable[[], date] = date.today,
    ):
        self.ephemeris, self.geocoder, self.knowledge, self.stitcher, self.today = ephemeris, geocoder, knowledge, stitcher, today

    def deps(self) -> Deps:
        return Deps(self.ephemeris, self.geocoder, self.knowledge(), self.today, self.stitcher(), settings.ALGORITHM_VERSION)

    def scenarios(self) -> list[Scenario]:
        return SCENARIOS

    def generation_steps(self) -> list[GenerationStep]:
        return STEPS

    def build(self, report_id: str, a: PersonInput, b: PersonInput) -> Report:
        return build_report(report_id, a, b, self.deps())

    def get_report(self, scenario: str) -> Report:
        if scenario == "error":
            raise ReportUnavailable("Ephemeris service timeout (demo)")
        key = scenario if scenario in {s.key for s in SCENARIOS} else "ideal"
        return self.build(f"demo-{key}", *demo_pair(key)).model_copy(update={"scenario": key})

    def quick_result(self, date_a: date, date_b: date) -> QuickResult:
        ca, cb = self.ephemeris.chart(BirthData(date_a)), self.ephemeris.chart(BirthData(date_b))
        pa, pb = num.profile(date_a, None, self.today()), num.profile(date_b, None, self.today())
        ra = role_for(astro_chart.dominant_element(ca), mode_from_life_path(pa.life_path))
        rb = role_for(astro_chart.dominant_element(cb), mode_from_life_path(pb.life_path))
        astro = astro_chart.score(ca, cb, astro_chart.synastry(ca, cb))
        numer, arc = num.score(pa, pb), tarot.score(date_a, date_b)
        combined = engine.combine({"astrology": astro, "psychology": None, "numerology": numer, "tarot": arc})
        cats = {
            "Страсть": ("flame", clamp(astro.categories["passion"] * 0.7 + arc.categories["passion"] * 0.3)),
            "Эмоции": ("heart", clamp(astro.categories["emotions"] * 0.6 + arc.categories["emotions"] * 0.2 + numer.score * 0.2)),
            "Коммуникация": ("message-circle", clamp(astro.categories["communication"] * 0.7 + numer.score * 0.3)),
        }
        a_arc, b_arc = tarot.arcana_of(date_a), tarot.arcana_of(date_b)

        def why(c: Chart, life_path: int, role: Role) -> list[str]:
            return [
                f"{astro_chart.element_counts(c)[role.element]} из 5 планет в стихии «{ELEMENTS[role.element]}» (Солнце в знаке {c.sign('Солнце')})",
                f"число пути {life_path} → {MODES[role.mode]}",
            ]

        return QuickResult(
            score=combined.total,
            pair_type=pair_name(ra, rb),
            role_a=ra.key,
            role_b=rb.key,
            dynamic=dynamic_for(ra, rb).key,
            why_a=why(ca, pa.life_path, ra),
            why_b=why(cb, pb.life_path, rb),
            pair_tagline=pair_tagline(ra, rb, "Вы", "партнёр"),
            sign_a=ca.sign("Солнце"),
            sign_b=cb.sign("Солнце"),
            categories=[QuickCategory(title=t, icon=i, score=s, tone=tone_of(s)) for t, (i, s) in cats.items()],
            arcana_a=arcana(a_arc),
            arcana_b=arcana(b_arc),
            arcana_pair=arcana(tarot.pair_arcana(a_arc, b_arc)),
        )
