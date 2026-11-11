# Деплой

Duoverse — один Docker-образ: gunicorn отдаёт и страницы, и статику (WhiteNoise), Celery-воркер запускается из того же образа. Нужны Postgres и Redis.

## Вариант 1. Один сервер (VPS) через Docker Compose

Подходит для старта: Caddy сам получает HTTPS-сертификат Let's Encrypt.

```bash
git clone https://github.com/deuteriumZzz/Duoverse.git && cd Duoverse
cp .env.example .env
```

Заполните в `.env` блок «production»:

| Переменная | Что это |
|---|---|
| `DJANGO_SECRET_KEY` | длинная случайная строка: `openssl rand -hex 32` |
| `DJANGO_DEBUG` | `0` |
| `DOMAIN` | домен, который смотрит на сервер (A-запись), например `duoverse.example.com` |
| `DJANGO_ALLOWED_HOSTS` | тот же домен |
| `POSTGRES_PASSWORD` | пароль базы: `openssl rand -hex 24` |
| `FIELD_ENCRYPTION_KEY` | ключ шифрования данных рождения и анкет (см. ниже). **Сохраните его отдельно**: без него данные не расшифровать |
| `EMAIL_URL` | SMTP для писем с кодом входа (российский сервис рассылок или почта на домене): `smtp+tls://user:pass@smtp.example.com:587` |
| `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET` | по желанию: кнопка «Войти с Яндекс ID». Redirect URI: `https://<домен>/login/yandex/callback/` |
| `VK_CLIENT_ID` (+ `VK_SERVICE_TOKEN` для конфиденциального приложения) | по желанию: «Войти с VK ID». Redirect: `https://<домен>/login/vk/callback/` |
| `TELEGRAM_BOT_NAME`, `TELEGRAM_BOT_TOKEN` | по желанию: вход через Telegram. В @BotFather: `/setdomain <домен>` |
| `TELEGRAM_WEBHOOK_SECRET` | случайная строка для уведомлений через бота; после запуска: `docker compose -f docker-compose.prod.yml exec web python manage.py telegram_setup` |
| `SITE_URL` | `https://<домен>` — для ссылок в уведомлениях и вебхука бота |
| `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` | магазин ЮKassa (сначала тестовый). В личном кабинете ЮKassa укажите HTTP-уведомления на `https://<домен>/yookassa/webhook/` для событий `payment.succeeded` и `payment.canceled` |
| `YOOKASSA_VAT_CODE` | код НДС для чека по вашей системе налогообложения (`1` — без НДС) |
| `PRICE_DEEP`, `PRICE_PLUS` | цены в рублях (по умолчанию 490 и 249) |
| `ANTHROPIC_API_KEY` | по желанию: без ключа отчёт собирается из базы знаний без ИИ-сшивки |

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # FIELD_ENCRYPTION_KEY
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser        # доступ к /staff/
```

Сервис `scheduler` раз в час чистит брошенные анонимные данные (старше 7 дней) и в `REMINDER_HOUR` шлёт напоминания в Telegram.

При каждом старте контейнер сам применяет миграции и подгружает базу знаний (`kb_seed` не трогает блоки, которые кто-то уже проверил в админке).

Обновление: `git pull && docker compose -f docker-compose.prod.yml up -d --build`.

## Вариант 2. PaaS (Render, Railway, Fly.io, Timeweb Cloud, Yandex Cloud)

1. Создайте Postgres и Redis в панели платформы.
2. Сервис **web** из `Dockerfile`, порт `8000` (или переменная `PORT`, если платформа задаёт свою). Health check: `/healthz`.
3. Сервис **worker** из того же образа, команда `celery -A config worker -l info`, переменная `RUN_MIGRATIONS=0`.
4. Переменные окружения: как в таблице выше, плюс `DATABASE_URL`, `CACHE_URL=redis://…/1`, `CELERY_BROKER_URL=redis://…/0` из панели платформы.
5. Если HTTPS завершается на балансировщике платформы, ничего менять не нужно: Django доверяет `X-Forwarded-Proto`.

## Что проверено

- `manage.py check --deploy` — без ошибок (HSTS-preload и `includeSubDomains` включайте сами, когда домен окончательно на HTTPS).
- `collectstatic` со сжатием, gunicorn с prod-настройками отвечает на `/healthz`, отдаёт отчёт и сжатую статику.
- CI собирает образ и проверяет, что контейнер отвечает на `/healthz`.

## Места рождения

При первом старте контейнер скачивает справочник GeoNames `cities500.zip` (~14 МБ, около 237 тыс. населённых пунктов, CC BY 4.0) и загружает в таблицу `GeoPlace`; русские названия берутся из `apps/compatibility/data/places_ru.tsv.gz` в репозитории. Обновить вручную: `docker compose -f docker-compose.prod.yml exec web python manage.py places_load`. Без этой таблицы приложение работает, но знает только ~30 городов. Карта и поиск идут только через наш сервер. Контуры карты (Natural Earth 1:50 млн и 1:10 млн, общественное достояние) лежат в `static/vendor/geo/`; пересобрать их: скачать четыре архива Natural Earth и запустить `npm run geo -- <папка>` (см. `scripts/build_geo.sh`).

## Резервные копии

Сервис `backup` раз в сутки кладёт снимок Postgres в `./backups/duoverse-ГГГГ-ММ-ДД.sql.gz` и хранит последние 14 дней (`BACKUP_KEEP_DAYS`). Неудачный снимок пишет в лог `BACKUP FAILED`: `docker compose -f docker-compose.prod.yml logs backup`.

Копии на том же сервере не спасут, если пропадёт сервер: раз в сутки забирайте `./backups` в другое место в России (например, объектное хранилище Selectel или Yandex Cloud через `rclone`).

Восстановление:

```bash
gunzip -c backups/duoverse-2026-11-11.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U duoverse duoverse
```

Без `FIELD_ENCRYPTION_KEY` бэкап бесполезен: храните ключ вне сервера (менеджер паролей).

## Ошибки и доступность

- Ошибки 500 приходят письмом на `ERROR_EMAILS` (через тот же `EMAIL_URL`). Введённые пользователем значения в письме скрыты.
- «Сайт упал» сервер сам о себе не сообщит: заведите внешнюю проверку `https://<домен>/healthz` раз в минуту (например, UptimeRobot или Яндекс Мониторинг) с уведомлением в Telegram.

## Перед публичным запуском

- **Лицензия Swiss Ephemeris** (`pyswisseph`): AGPL или коммерческая лицензия Astrodienst. Для закрытого коммерческого сервиса нужна коммерческая.
- Политика, согласие и оферта (`/privacy/`, `/consent/`, `/terms/`) собираются из `docs/legal/` — это черновики, их должен посмотреть юрист. Чек-лист — `docs/legal/README.md`.
- Почта для ссылок входа: настройте SPF/DKIM у домена, иначе письма уйдут в спам.
