from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import ExpenseCategory, ExpenseReport, ExpenseItem, ExpenseReceipt, MileageEntry


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "active",
        "template_column",
        "requires_client",
        "receipt_required_threshold",
    )
    list_filter = ("active", "requires_client")
    search_fields = ("name",)
    ordering = ("name",)


class ExpenseReceiptInline(admin.TabularInline):
    model = ExpenseReceipt
    extra = 0
    fields = ("file", "original_filename", "uploaded_at")
    readonly_fields = ("uploaded_at",)


class ExpenseItemInline(admin.TabularInline):
    model = ExpenseItem
    extra = 0
    fields = (
        "date",
        "category",
        "amount",
        "description",
        "client",
        "paper_receipt_delivered",
        "receipt_requirement_met",
    )
    readonly_fields = ("receipt_requirement_met",)
    ordering = ("date",)
    show_change_link = True

    @admin.display(boolean=True, description="Receipt OK")
    def receipt_requirement_met(self, obj):
        if obj.pk:
            return obj.receipt_requirement_met
        return True


class MileageEntryInline(admin.TabularInline):
    model = MileageEntry
    extra = 0
    fields = ("date", "miles", "description", "rate_override", "total_amount")
    readonly_fields = ("total_amount",)
    ordering = ("date",)

    @admin.display(description="Amount")
    def total_amount(self, obj):
        if obj.pk:
            return f"${obj.total_amount:.2f}"
        return "-"


@admin.register(ExpenseReport)
class ExpenseReportAdmin(SimpleHistoryAdmin):
    list_display = (
        "employee",
        "month",
        "status",
        "total_expenses",
        "total_mileage_amount",
        "grand_total",
        "submitted_at",
    )
    list_filter = ("status", "month__year", "month__month")
    search_fields = ("employee__email", "employee__first_name", "employee__last_name")
    ordering = ("-month__year", "-month__month", "employee__email")
    raw_id_fields = ("employee", "approved_by")
    date_hierarchy = "month__start_date"
    inlines = [ExpenseItemInline, MileageEntryInline]

    fieldsets = (
        (None, {"fields": ("employee", "month", "status")}),
        ("Notes", {"fields": ("employee_notes", "reviewer_notes")}),
        ("Review", {"fields": ("submitted_at", "approved_at", "approved_by")}),
    )

    readonly_fields = ("submitted_at", "approved_at")

    @admin.display(description="Expenses")
    def total_expenses(self, obj):
        return f"${obj.total_expenses:.2f}"

    @admin.display(description="Mileage")
    def total_mileage_amount(self, obj):
        return f"${obj.total_mileage_amount:.2f}"

    @admin.display(description="Total")
    def grand_total(self, obj):
        return f"${obj.grand_total:.2f}"


@admin.register(ExpenseItem)
class ExpenseItemAdmin(SimpleHistoryAdmin):
    list_display = (
        "report",
        "date",
        "category",
        "amount",
        "description",
        "receipt_requirement_met",
    )
    list_filter = ("category", "date")
    search_fields = ("report__employee__email", "description", "client")
    ordering = ("-date",)
    raw_id_fields = ("report",)
    date_hierarchy = "date"
    inlines = [ExpenseReceiptInline]

    @admin.display(boolean=True, description="Receipt OK")
    def receipt_requirement_met(self, obj):
        return obj.receipt_requirement_met


@admin.register(MileageEntry)
class MileageEntryAdmin(SimpleHistoryAdmin):
    list_display = ("report", "date", "miles", "rate", "total_amount", "description")
    list_filter = ("date",)
    search_fields = ("report__employee__email", "description")
    ordering = ("-date",)
    raw_id_fields = ("report",)
    date_hierarchy = "date"

    @admin.display(description="Rate")
    def rate(self, obj):
        return f"${obj.rate:.3f}"

    @admin.display(description="Amount")
    def total_amount(self, obj):
        return f"${obj.total_amount:.2f}"
