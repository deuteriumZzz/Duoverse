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
| `EMAIL_URL` | SMTP для писем со ссылкой входа: `smtp+tls://user:pass@smtp.example.com:587` |
| `ANTHROPIC_API_KEY` | по желанию: без ключа отчёт собирается из базы знаний без ИИ-сшивки |

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # FIELD_ENCRYPTION_KEY
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser        # доступ к /staff/
```

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

## Резервные копии

Всё ценное — в Postgres. Снимок:

```bash
docker compose -f docker-compose.prod.yml exec db pg_dump -U duoverse duoverse | gzip > backup-$(date +%F).sql.gz
```

Без `FIELD_ENCRYPTION_KEY` бэкап бесполезен: храните ключ вне сервера (менеджер паролей).

## Перед публичным запуском

- **Лицензия Swiss Ephemeris** (`pyswisseph`): AGPL или коммерческая лицензия Astrodienst. Для закрытого коммерческого сервиса нужна коммерческая.
- Политика конфиденциальности и согласие на обработку данных (152-ФЗ / GDPR): тексты в `/disclaimer/` — черновик, их должен посмотреть юрист.
- Почта для ссылок входа: настройте SPF/DKIM у домена, иначе письма уйдут в спам.
