from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin

from .models import User, EmployeeProfile


class EmployeeProfileInline(admin.StackedInline):
    model = EmployeeProfile
    can_delete = False
    verbose_name_plural = "Employee Profile"
    fk_name = "user"
    fieldsets = (
        (None, {
            "fields": ("employee_id", "title", "department", "seniority_order")
        }),
        ("Employment Status", {
            "fields": ("hire_date", "termination_date", "is_exempt"),
            "classes": ("collapse",),
        }),
        ("Contact Info", {
            "fields": ("phone", "emergency_contact_name", "emergency_contact_phone"),
            "classes": ("collapse",),
        }),
        ("Expense Settings", {
            "fields": ("mileage_rate",),
            "classes": ("collapse",),
        }),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin, SimpleHistoryAdmin):
    """Admin configuration for custom User model."""

    list_display = ("email", "first_name", "last_name", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "first_name", "last_name"),
            },
        ),
    )

    readonly_fields = ("date_joined", "last_login")
    inlines = [EmployeeProfileInline]

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        return super().get_inline_instances(request, obj)


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(SimpleHistoryAdmin):
    """Standalone admin for EmployeeProfile."""

    list_display = (
        "user",
        "employee_id",
        "title",
        "department",
        "seniority_order",
        "is_active_employee",
    )
    list_filter = ("department", "is_exempt")
    search_fields = ("user__email", "user__first_name", "user__last_name", "employee_id")
    ordering = ("seniority_order", "user__last_name")
    raw_id_fields = ("user",)

    fieldsets = (
        (None, {"fields": ("user", "employee_id", "title", "department", "seniority_order")}),
        ("Employment Status", {"fields": ("hire_date", "termination_date", "is_exempt")}),
        ("Contact", {"fields": ("phone", "emergency_contact_name", "emergency_contact_phone")}),
        ("Expense Settings", {"fields": ("mileage_rate",)}),
    )

    @admin.display(boolean=True, description="Active")
    def is_active_employee(self, obj):
        return obj.is_active_employee
