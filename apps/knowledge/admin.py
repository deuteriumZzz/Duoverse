from django.contrib import admin
from django.utils import timezone

from .models import KnowledgeBlock


@admin.register(KnowledgeBlock)
class KnowledgeBlockAdmin(admin.ModelAdmin):
    list_display = ("key", "locale", "domain", "status", "evidence_level", "version", "reviewed_by", "updated_at")
    list_filter = ("status", "domain", "locale", "evidence_level")
    search_fields = ("key", "text")
    actions = ["mark_reviewed", "publish"]

    @admin.action(description="Отметить «проверено»")
    def mark_reviewed(self, request, queryset):
        queryset.update(status=KnowledgeBlock.Status.REVIEWED, reviewed_by=request.user.get_username(), reviewed_at=timezone.now())

    @admin.action(description="Опубликовать")
    def publish(self, request, queryset):
        queryset.filter(status=KnowledgeBlock.Status.REVIEWED).update(status=KnowledgeBlock.Status.PUBLISHED)
