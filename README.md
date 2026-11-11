<p align="center">
  <img src="docs/assets/banner.jpg" alt="Duoverse — совместимость, у которой есть объяснение" width="100%">
</p>

<p align="center">
  <a href="https://github.com/deuteriumZzz/Duoverse/actions/workflows/ci.yml"><img src="https://github.com/deuteriumZzz/Duoverse/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12-1e1a16?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/django-5.2-1e1a16?logo=django&logoColor=white" alt="Django 5.2">
  <img src="https://img.shields.io/badge/htmx-2-1e1a16" alt="htmx 2">
  <img src="https://img.shields.io/badge/alpine.js-3-1e1a16?logo=alpinedotjs&logoColor=white" alt="Alpine.js 3">
  <img src="https://img.shields.io/badge/tailwind-4-1e1a16?logo=tailwindcss&logoColor=white" alt="Tailwind 4">
  <img src="https://img.shields.io/badge/docker-ready-1e1a16?logo=docker&logoColor=white" alt="Docker ready">
</p>

<p align="center">
  <b>Разбор пары в четырёх «вселенных»: астрология, числа, таро и психология.</b><br>
  Не «вы совместимы на 78 %», а что именно у вас хорошо, где будут ссоры и что с этим делать — простым языком.
</p>

<p align="center">
  <a href="#-демо">Демо</a> ·
  <a href="#-что-внутри">Что внутри</a> ·
  <a href="#-как-это-считается">Как это считается</a> ·
  <a href="#-быстрый-старт">Быстрый старт</a> ·
  <a href="#-деплой">Деплой</a> ·
  <a href="#-архитектура">Архитектура</a> ·
  <a href="#-документация">Документация</a>
</p>

---

## ✦ Демо

<table>
  <tr>
    <td width="34%" align="center"><img src="docs/assets/demo.gif" alt="Отчёт открывается, созвездия двух карт сходятся в созвездие пары" width="300"></td>
    <td width="66%">
      <img src="docs/assets/report-overview.jpg" alt="Итог: тип пары, общий балл, сводка">
      <p align="center"><sub>Итог: один из 78 типов пар, балл по четырём вселенным и сводка, собранная из проверенных текстов</sub></p>
    </td>
  </tr>
</table>

<table>
  <tr>
    <td align="center"><img src="docs/assets/m-overview.jpg" alt="Итог на телефоне" width="200"><br><sub>Итог</sub></td>
    <td align="center"><img src="docs/assets/m-razbor.jpg" alt="Разбор сферы" width="200"><br><sub>Разбор по сферам</sub></td>
    <td align="center"><img src="docs/assets/m-tarot.jpg" alt="Таро" width="200"><br><sub>Таро</sub></td>
    <td align="center"><img src="docs/assets/m-daily.jpg" alt="План привычек на неделю" width="200"><br><sub>План на неделю</sub></td>
  </tr>
</table>

<details>
<summary><b>Ещё экраны</b></summary>
<br>

| Лендинг | Две карты: биколесо и таблицы планет |
|---|---|
| <img src="docs/assets/landing.jpg" alt="Лендинг"> | <img src="docs/assets/astrology-wheel.jpg" alt="Биколесо синастрии"> |
| **Из чего сложилось: четыре слоя** | |
| <img src="docs/assets/layers.jpg" alt="Слои расчёта"> | |

</details>

## ✦ Что внутри

**Для пары**

- **Итог за минуту.** Тип пары (12 ролей → 78 типов), балл, точность разбора и то, что её повысит.
- **Разбор по 13 сферам:** притяжение, секс (за подтверждением 18+), эмоции, разговоры, конфликты, доверие, власть, тени, дом, деньги, планы, люди, рост. В каждой сфере — история вашей пары, сценарий ссоры, упражнение, вопрос для разговора и факторы из всех слоёв.
- **Из чего сложилось.** Полные карты: биколесо, сетка аспектов (мажорные и минорные), наложение домов, композит, баланс стихий; Big Five, привязанность и стиль конфликта; числа и Матрица; арканы.
- **Сегодня — на двоих.** Вопрос дня (364 вопроса по 13 сферам, с упором на слабые сферы пары): каждый отвечает со своего телефона, ответ партнёра открывается, когда ответили оба. Квиз недели — сравните, где вы совпадаете. Уведомления в Telegram или на почту.
- **Вместе.** Микропривычки, выросшие из слабых сфер пары. Пара берёт 2–3 на неделю и отмечает их во вкладке «Сегодня».
- **Тарифы.** Итог, вопрос дня и приглашение партнёра бесплатно. Полный разбор — 490 ₽ разово, открывается обоим. «Пара+» — 249 ₽ на 30 дней без автосписаний: все пары, квизы, история ответов. Оплата через ЮKassa с чеком по 54-ФЗ.
- **Вход без пароля.** Почта с кодом из 6 цифр, Яндекс ID, VK ID или Telegram. Партнёр подключается по ссылке, коду или QR и видит только вашу пару: общий разбор и план. Устройства, выгрузка и удаление данных — в «Мои данные».

**Для разработчика**

- Каждое число в отчёте посчитано: Swiss Ephemeris, пифагорейская нумерология с мастер-числами, редукция арканов, психометрические шкалы, движок весов. Отчёт — снимок, привязанный к версии алгоритма.
- Тексты — из базы знаний с модерацией (`draft → reviewed → published`). ИИ (Claude) только сшивает проверенные блоки, а пост-валидатор отклоняет ответ с выдуманными планетами и аспектами. Без ключа API отчёт собирается из блоков без ИИ.
- Чистая архитектура: расчёты — чистые функции в `domain/`, сборка — в `application/`, Django — только снаружи.

## ✦ Как это считается

| Вселенная | Слой | Вес | Что даёт |
|---|---|---|---|
| Астрология | символический | 35 % | синастрия, наложение домов, композит |
| Психология | научный | 35 % | Big Five (Mini-IPIP), привязанность, конфликт (по Готтману) |
| Числа | символический | 15 % | жизненный путь, число пары, Матрица |
| Таро | символический | 15 % | арканы рождения и аркан пары |

- **Нет слоя — его вес делится между остальными.** Человек может поменять веса сам («не верю в таро»).
- **Индекс согласия** показывает, насколько вселенные сходятся между собой: высокий балл при низком согласии — повод для осторожности.
- **Точность разбора зависит от данных:** только даты → + время и место рождения (дома, Асцендент, точная Луна) → + анкеты обоих (научный слой). Точность — это то, насколько полно мы знаем пару, а не вероятность её успеха.
- **Этика.** Никаких вердиктов, прогнозов и диагнозов; символический слой честно подписан как символический. Методика каждой вселенной описана в [`docs/methodology/`](docs/methodology).

## ✦ Быстрый старт

Нужны Python 3.12, Node 22 и [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/deuteriumZzz/Duoverse.git && cd Duoverse
uv venv --python 3.12 .venv && uv pip install --python .venv -r pyproject.toml --group dev
npm install && npm run build           # иконки + Tailwind → static/dist/app.css
cp .env.example .env                   # ANTHROPIC_API_KEY — по желанию
.venv/bin/python manage.py migrate     # база + сид базы знаний
.venv/bin/python manage.py runserver   # → http://localhost:8000
```

С Postgres, Redis и Celery: `docker compose up`.

| Команда | Что делает |
|---|---|
| `npm run watch` | пересборка CSS при правках шаблонов |
| `.venv/bin/python -m pytest` | тесты: расчёты, сборка отчёта, сценарии от мастера до удаления данных |
| `.venv/bin/python manage.py kb_coverage` | каких текстов не хватает в базе знаний |
| `.venv/bin/python manage.py kb_draft --dry-run` | сколько черновиков допишет Claude (пакетный режим API, нужен `ANTHROPIC_API_KEY`); без `--dry-run` — пишет их со статусом «черновик» для проверки в `/staff/` |
| `.venv/bin/python manage.py createsuperuser` | доступ к админке базы знаний `/staff/` |

Демо-отчёт открыт на `/report/`. Сценарии (идеальная и сложная пара, нет времени рождения, нет анкет, только даты, ошибка) переключаются скрытой плашкой: `?dev=1` включает её, `?dev=0` выключает (только при `DEBUG`).

## ✦ Деплой

Один образ, который сам отдаёт статику, плюс Postgres, Redis и Celery-воркер. Для одного сервера есть готовый compose с автоматическим HTTPS (Caddy):

```bash
cp .env.example .env    # заполните блок «production»
docker compose -f docker-compose.prod.yml up -d --build
```

Пошагово, включая PaaS, бэкапы и чек-лист перед запуском: [**docs/DEPLOY.md**](docs/DEPLOY.md).

## ✦ Архитектура

```mermaid
flowchart LR
    U([Пара]) -->|даты, время, место, анкеты| W[apps/web<br/>тонкие views + htmx]
    W --> S[compatibility/services<br/>устройство-владелец, пары, снимки]
    S -->|Celery| B[application/build_report]
    B --> A[astrology]
    B --> N[numerology]
    B --> T[tarot]
    B --> P[psychology]
    B --> K[(knowledge<br/>база знаний)]
    B --> I[insights<br/>Claude + валидатор]
    B --> R[[Report<br/>pydantic-снимок]]
    R --> W
```

| Путь | Что |
|---|---|
| `apps/compatibility/domain/report.py` | контракт отчёта (pydantic) |
| `apps/compatibility/application/build_report.py` | сборка отчёта из расчётов и базы знаний |
| `apps/{astrology,numerology,tarot,psychology}/domain/` | расчёты вселенных — чистые функции |
| `apps/compatibility/models.py`, `services.py`, `tasks.py`, `plan.py` | устройство-владелец, пары, снимки, подписанные ссылки, Celery, план привычек |
| `apps/knowledge/` | база знаний, сид, `kb_coverage` |
| `apps/insights/` | ИИ-сшивка: промпт, вызов Claude, валидатор |
| `apps/web/` | views, URL, template tags (иконки, радар, биколесо, постеры пар) |
| `templates/components/` | компоненты интерфейса, один компонент — один файл |
| `static/src/app.css` | дизайн-токены и motion-система |

**Стек:** Django 5.2 · htmx 2 · Alpine.js 3 · Tailwind CSS 4 · pydantic 2 · Celery + Redis · PostgreSQL · pyswisseph · Anthropic SDK · WhiteNoise · gunicorn · Docker · GitHub Actions (ruff, mypy, pytest, сборка образа).

## ✦ Документация

| Документ | О чём |
|---|---|
| [`docs/methodology/`](docs/methodology) | как считается каждая вселенная и типы пар |
| [`docs/product/REPORT_SPEC.md`](docs/product/REPORT_SPEC.md) | что и зачем есть в отчёте |
| [`docs/ui/SCREEN_MAP.md`](docs/ui/SCREEN_MAP.md) | карта экранов и состояний |
| [`docs/design/DESIGN_SYSTEM.md`](docs/design/DESIGN_SYSTEM.md) | дизайн-система и motion |
| [`docs/contracts/report.md`](docs/contracts/report.md) | контракт данных отчёта |
| [`docs/adr/`](docs/adr) | архитектурные решения |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | деплой |

## ✦ Приватность

Дата, время и место рождения, ответы анкет и почта шифруются в базе (Fernet); для поиска аккаунта хранится только ключевой хэш почты. Вход без паролей, каждое устройство можно отключить. Партнёр видит общий разбор пары, но не ваши ответы анкеты и не другие разборы. Данные можно выгрузить и удалить одной кнопкой; ссылки «поделиться» показывают только карточку пары. Подробнее: [ADR-0010](docs/adr/0010-accounts-and-pairs.md).

## ✦ Лицензии

Астрономические расчёты используют [Swiss Ephemeris](https://www.astro.com/swisseph/) через `pyswisseph`: AGPL или коммерческая лицензия Astrodienst. Лицензию самого проекта выбирает владелец репозитория.

<p align="center"><sub>Астрология, числа и таро — символический слой для размышления, не наука. Психология опирается на исследования. Duoverse не ставит диагнозов и не принимает решений за вас.</sub></p>
