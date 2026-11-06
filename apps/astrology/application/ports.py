from typing import Protocol

from apps.astrology.domain.chart import BirthData, Chart, Place


class EphemerisProvider(Protocol):
    def chart(self, birth: BirthData) -> Chart: ...


class Geocoder(Protocol):
    def lookup(self, name: str) -> Place | None: ...

    def names(self) -> list[str]: ...
