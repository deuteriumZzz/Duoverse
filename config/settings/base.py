"""Shared settings. Environment-specific overrides live in dev.py / prod.py / test.py."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "testserver"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.web",
    "apps.compatibility",
    "apps.knowledge",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "django.contrib.auth.context_processors.auth",
                "apps.web.context.prototype",
            ],
            "builtins": ["apps.web.templatetags.ui", "apps.web.templatetags.art"],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL in docker-compose / prod; SQLite only as a zero-setup local fallback.
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}

# Celery: Redis broker; without a broker tasks run inline (dev/test)
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="")
CELERY_TASK_ALWAYS_EAGER = not CELERY_BROKER_URL
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 120

ALGORITHM_VERSION = "0.3.1"

FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")  # Fernet key; derived from SECRET_KEY when empty
KB_ALLOWED_STATUSES = env.list("KB_ALLOWED_STATUSES", default=["published"])
OWNER_COOKIE = "dv_owner"
OWNER_COOKIE_AGE = 60 * 60 * 24 * 365
SHARE_LINK_MAX_AGE = 60 * 60 * 24 * 30
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Duoverse <hello@duoverse.app>")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
LLM_MODEL = env("LLM_MODEL", default="claude-opus-5-5")
LLM_EFFORT = env("LLM_EFFORT", default="medium")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

LANGUAGE_CODE = "ru"
LANGUAGES = [("ru", "Русский"), ("en", "English")]
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
