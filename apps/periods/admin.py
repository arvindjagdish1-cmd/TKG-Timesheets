from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import TimesheetPeriod, ExpenseMonth


@admin.register(TimesheetPeriod)
class TimesheetPeriodAdmin(SimpleHistoryAdmin):
    list_display = (
        "display_name",
        "start_date",
        "end_date",
        "due_date",
        "is_locked",
        "is_past_due",
    )
    list_filter = ("year", "half", "is_locked")
    search_fields = ("year",)
    ordering = ("-year", "-month", "-half")
    date_hierarchy = "start_date"

    fieldsets = (
        (None, {"fields": ("year", "month", "half")}),
        ("Dates", {"fields": ("start_date", "end_date", "due_date", "reminder_date")}),
        ("Status", {"fields": ("is_locked", "locked_at", "locked_by")}),
    )

    readonly_fields = ("locked_at", "locked_by")

    @admin.display(boolean=True, description="Past Due")
    def is_past_due(self, obj):
        return obj.is_past_due


@admin.register(ExpenseMonth)
class ExpenseMonthAdmin(SimpleHistoryAdmin):
    list_display = (
        "display_name",
        "start_date",
        "end_date",
        "due_date",
        "is_locked",
        "is_past_due",
    )
    list_filter = ("year", "is_locked")
    search_fields = ("year",)
    ordering = ("-year", "-month")
    date_hierarchy = "start_date"

    fieldsets = (
        (None, {"fields": ("year", "month")}),
        ("Dates", {"fields": ("start_date", "end_date", "due_date", "reminder_date")}),
        ("Status", {"fields": ("is_locked", "locked_at", "locked_by")}),
    )

    readonly_fields = ("locked_at", "locked_by")

    @admin.display(boolean=True, description="Past Due")
    def is_past_due(self, obj):
        return obj.is_past_due
