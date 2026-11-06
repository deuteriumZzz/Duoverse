from .base import *  # noqa: F403
from .base import env

DEBUG = True  # the prototype UI hides dev tools unless DEBUG; tests exercise them
DATABASES = {"default": env.db("DATABASE_URL", default="sqlite://:memory:")}
CELERY_TASK_ALWAYS_EAGER = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
KB_ALLOWED_STATUSES = ["draft", "reviewed", "published"]
ANTHROPIC_API_KEY = ""  # tests never call the network
