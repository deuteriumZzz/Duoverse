from datetime import date
from typing import Protocol

from apps.compatibility.domain.report import GenerationStep, QuickResult, Report, Scenario


class ReportProvider(Protocol):
    def scenarios(self) -> list[Scenario]: ...

    def get_report(self, scenario: str) -> Report: ...

    def quick_result(self, date_a: date, date_b: date) -> QuickResult: ...

    def generation_steps(self) -> list[GenerationStep]: ...
