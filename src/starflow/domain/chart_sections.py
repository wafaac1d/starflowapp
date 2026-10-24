"""Текстовые разделы карты. Дома и асцендент появляются только из расчёта."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ChartSection:
    id: str
    title: str
    body: str


def _titled(value: str) -> str:
    for index, char in enumerate(value):
        if char.isalpha():
            return value[:index] + char.upper() + value[index + 1 :]
    return value


def chart_sections(
    *,
    sun_sign: str | None,
    moon_sign: str | None,
    ascendant_sign: str | None,
    houses: tuple[str, ...] | None,
    planets: tuple[tuple[str, str | None], ...],
    aspects: tuple[str, ...],
    line: Callable[[str], str],
) -> tuple[ChartSection, ...]:
    sections: list[ChartSection] = []
    if sun_sign is not None:
        sections.append(
            ChartSection(
                "sun",
                line("ui.chart.section_sun"),
                line("ui.chart.section_sun_body").replace("{sign}", _titled(sun_sign)),
            )
        )
    if moon_sign is not None:
        sections.append(
            ChartSection(
                "moon",
                line("ui.chart.section_moon"),
                line("ui.chart.section_moon_body").replace("{sign}", _titled(moon_sign)),
            )
        )
    if ascendant_sign is not None:
        sections.append(
            ChartSection(
                "asc",
                line("ui.chart.section_asc"),
                line("ui.chart.section_asc_body").replace("{sign}", _titled(ascendant_sign)),
            )
        )
    if houses is not None:
        rendered = ", ".join(
            f"{index}. {_titled(sign)}" for index, sign in enumerate(houses, start=1)
        )
        sections.append(
            ChartSection(
                "houses",
                line("ui.chart.section_houses"),
                line("ui.chart.section_houses_body").replace("{houses}", rendered),
            )
        )
    if planets:
        lines = [
            _titled(name) if sign is None else f"{_titled(name)}, {_titled(sign)}"
            for name, sign in planets
        ]
        sections.append(ChartSection("planets", line("ui.chart.section_planets"), "; ".join(lines)))
    if aspects:
        sections.append(
            ChartSection(
                "aspects",
                line("ui.chart.section_aspects"),
                "; ".join(_titled(item) for item in aspects),
            )
        )
    return tuple(sections)
