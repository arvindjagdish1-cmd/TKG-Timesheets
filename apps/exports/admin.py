from django.contrib import admin

from .models import ExportJob, ExportDownload


class ExportDownloadInline(admin.TabularInline):
    model = ExportDownload
    extra = 0
    fields = ("downloaded_by", "downloaded_at", "ip_address")
    readonly_fields = ("downloaded_by", "downloaded_at", "ip_address")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = (
        "export_type",
        "year",
        "month",
        "half",
        "employee",
        "status",
        "created_by",
        "created_at",
    )
    list_filter = ("export_type", "status", "year", "month")
    search_fields = ("employee__email", "filename")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    inlines = [ExportDownloadInline]

    fieldsets = (
        (None, {"fields": ("export_type", "status")}),
        ("Scope", {"fields": ("year", "month", "half", "employee")}),
        ("Output", {"fields": ("file", "filename", "error_message")}),
        ("Metadata", {"fields": ("created_by", "created_at", "completed_at")}),
    )

    readonly_fields = ("created_at", "completed_at")


@admin.register(ExportDownload)
class ExportDownloadAdmin(admin.ModelAdmin):
    list_display = ("export", "downloaded_by", "downloaded_at", "ip_address")
    list_filter = ("downloaded_at",)
    search_fields = ("downloaded_by__email", "export__filename")
    ordering = ("-downloaded_at",)
    date_hierarchy = "downloaded_at"
    readonly_fields = ("export", "downloaded_by", "downloaded_at", "ip_address", "user_agent")
