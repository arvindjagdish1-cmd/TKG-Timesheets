from django.contrib import admin

from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "notification_type",
        "recipient",
        "subject",
        "sent_at",
        "created_at",
    )
    list_filter = ("notification_type", "sent_at")
    search_fields = ("recipient__email", "subject")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("notification_type", "recipient")}),
        ("Content", {"fields": ("subject", "body")}),
        ("Delivery", {"fields": ("sent_at", "error_message")}),
    )

    readonly_fields = ("created_at", "sent_at")
