from .base import *  # noqa: F403
from .base import MIDDLEWARE, env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")  # required, no default
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # required: your domain(s)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[f"https://{h}" for h in ALLOWED_HOSTS])
# Required separately from SECRET_KEY: rotating the secret key must not make stored birth data unreadable.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]  # platform health checks come over plain HTTP
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_CONTENT_TYPE_NOSNIFF = True

# gunicorn serves /static/ itself (compressed, cached), no nginx needed
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]

# Hashless compressed storage: static/src (Tailwind input) is not post-processed, and templates
# version CSS/JS/sprite URLs themselves with ?v=<mtime> (see the `asset` template tag).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

if email_url := env("EMAIL_URL", default=""):  # e.g. smtp+tls://user:pass@smtp.example.com:587 — magic links
    vars().update(env.email_url_config(email_url))
