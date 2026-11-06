# Контракт: Report

Источник истины — pydantic-модели в `apps/compatibility/domain/report.py`. Фикстуры в `apps/compatibility/infrastructure/fixtures/*.json` валидируются ими при каждом запросе, поэтому расхождение контракта и данных падает сразу (и в тестах).

## ReportProvider

| Метод | Возвращает | Экран |
|---|---|---|
| `get_report(scenario)` | `Report` или `ReportUnavailable` | отчёт и все вкладки, веса, «Сегодня», PDF, шеринг |
| `quick_result(date_a, date_b)` | `QuickResult` | мини-демо на лендинге, быстрый старт |
| `generation_steps()` | `list[GenerationStep]` | экран генерации (htmx-поллинг) |
| `history()` | `list[ReportSummary]` | история |
| `profiles()` | `list[Partner]` | профили |
| `scenarios()` | `list[Scenario]` | dev-переключатель |

## Ключевые правила

- Баллы — целые 0–100. `None` у вселенной = слой не посчитан (нет данных); `missing` объясняет почему.
- `weight` у вселенных — уже перераспределённые веса (сумма 100 по посчитанным слоям).
- Каждое утверждение, которое видит пользователь, несёт `evidence: list[Evidence]` — источник, деталь, вклад, слой (`symbolic` / `scientific`). UI показывает их в «Почему так».
- `tone`: `synergy | neutral | attention | risk` — всегда рисуется цветом **и** иконкой с подписью.
- `accuracy.missing` — человеческие строки о том, что не учтено; при непустом списке отчёт показывает баннер точности.
- `algorithm_version` выводится в отчёте и PDF.
- `pair_type.role_a / role_b / dynamic` и `why_a / why_b` — роли партнёров и основания (см. `docs/methodology/pair-typology.md`); постер строится из ролей. В `QuickResult` те же поля, `why_*` — строки.
- `astrology.planets_a/planets_b` — эклиптические долготы (0–360°) для анимации созвездий; аспекты рисуются только между планетами, которые есть в этих списках.
- Даты — ISO `YYYY-MM-DD`, время — `HH:MM`.

## Сценарии-фикстуры

`ideal` — полный набор. Остальные наследуют его через `"extends"` и переопределяют поля (глубокое слияние словарей, списки заменяются целиком):
`complex` (низкое согласие вселенных), `no_time`, `no_psych`, `dates_only`; `error` → `ReportUnavailable`.
