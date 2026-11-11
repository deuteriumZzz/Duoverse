# ── 1. assets: Tailwind CSS (the icon sprite is committed, rebuilt with `npm run build`) ──
FROM node:22-slim AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY static/src static/src
COPY templates templates
COPY apps apps
RUN npx tailwindcss -i static/src/app.css -o static/dist/app.css --minify

# ── 2. app ──
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    WEB_CONCURRENCY=3 PORT=8000
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
# pyswisseph ships no Linux wheel: a compiler only for the install, then it goes
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libc6-dev \
 && uv pip install --system --no-cache -r pyproject.toml \
 && apt-get purge -y gcc g++ libc6-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY . .
COPY --from=assets /app/static/dist static/dist
# collectstatic needs no real secrets; the build-time values never reach the running container
RUN DJANGO_SECRET_KEY=build DJANGO_ALLOWED_HOSTS=build FIELD_ENCRYPTION_KEY=build python manage.py collectstatic --noinput \
 && useradd --create-home --uid 1000 app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz', timeout=4)"
ENTRYPOINT ["scripts/docker-entrypoint.sh"]
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --access-logfile - --timeout 60"]
