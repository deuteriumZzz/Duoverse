from django.apps import AppConfig


class CompatibilityConfig(AppConfig):
    name = "apps.compatibility"
    label = "compatibility"
    default_auto_field = "django.db.models.BigAutoField"
