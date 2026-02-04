from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import ChargeCode, Timesheet, TimesheetLine, TimeEntry, TimesheetUpload, ClientMapping


@admin.register(ChargeCode)
class ChargeCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "active", "is_client_work")
    list_filter = ("active", "is_client_work")
    search_fields = ("code", "description")
    ordering = ("code",)


class TimeEntryInline(admin.TabularInline):
    model = TimeEntry
    extra = 0
    fields = ("date", "hours")
    ordering = ("date",)


class TimesheetLineInline(admin.TabularInline):
    model = TimesheetLine
    extra = 0
    fields = ("charge_code", "label", "order", "total_hours")
    readonly_fields = ("total_hours",)
    ordering = ("order", "id")
    show_change_link = True

    @admin.display(description="Total Hours")
    def total_hours(self, obj):
        if obj.pk:
            return obj.total_hours
        return "-"


@admin.register(Timesheet)
class TimesheetAdmin(SimpleHistoryAdmin):
    list_display = (
        "employee",
        "period",
        "status",
        "total_hours",
        "submitted_at",
        "approved_by",
    )
    list_filter = ("status", "period__year", "period__month", "period__half")
    search_fields = ("employee__email", "employee__first_name", "employee__last_name")
    ordering = ("-period__year", "-period__month", "employee__email")
    raw_id_fields = ("employee", "approved_by")
    date_hierarchy = "period__start_date"
    inlines = [TimesheetLineInline]

    fieldsets = (
        (None, {"fields": ("employee", "period", "status")}),
        ("Notes", {"fields": ("employee_notes", "reviewer_notes")}),
        ("Review", {"fields": ("submitted_at", "approved_at", "approved_by")}),
    )

    readonly_fields = ("submitted_at", "approved_at")

    @admin.display(description="Total Hours")
    def total_hours(self, obj):
        return obj.total_hours


@admin.register(TimesheetLine)
class TimesheetLineAdmin(admin.ModelAdmin):
    list_display = ("timesheet", "charge_code", "label", "total_hours", "order")
    list_filter = ("charge_code",)
    search_fields = ("timesheet__employee__email", "label")
    ordering = ("timesheet", "order")
    raw_id_fields = ("timesheet",)
    inlines = [TimeEntryInline]

    @admin.display(description="Total Hours")
    def total_hours(self, obj):
        return obj.total_hours


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ("line", "date", "hours")
    list_filter = ("date",)
    search_fields = ("line__timesheet__employee__email",)
    ordering = ("-date",)
    raw_id_fields = ("line",)
    date_hierarchy = "date"


@admin.register(ClientMapping)
class ClientMappingAdmin(admin.ModelAdmin):
    list_display = ("code", "display_name", "sort_order", "active")
    list_filter = ("active",)
    search_fields = ("code", "display_name")
    ordering = ("sort_order", "display_name")


@admin.register(TimesheetUpload)
class TimesheetUploadAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "year",
        "month",
        "status",
        "has_blocking_errors",
        "reviewed_by",
        "uploaded_at",
    )
    list_filter = ("status", "year", "month", "has_blocking_errors")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    ordering = ("-year", "-month", "-uploaded_at")
    raw_id_fields = ("user",)
