from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = "Create default role groups with appropriate permissions."

    def handle(self, *args, **options):
        # Define groups and their permissions
        role_permissions = {
            "employees": [
                # Timesheets - own only (enforced at view level)
                ("timesheets", "timesheet", "view_timesheet"),
                ("timesheets", "timesheet", "add_timesheet"),
                ("timesheets", "timesheet", "change_timesheet"),
                ("timesheets", "timesheetline", "view_timesheetline"),
                ("timesheets", "timesheetline", "add_timesheetline"),
                ("timesheets", "timesheetline", "change_timesheetline"),
                ("timesheets", "timesheetline", "delete_timesheetline"),
                ("timesheets", "timeentry", "view_timeentry"),
                ("timesheets", "timeentry", "add_timeentry"),
                ("timesheets", "timeentry", "change_timeentry"),
                ("timesheets", "timeentry", "delete_timeentry"),
                ("timesheets", "chargecode", "view_chargecode"),
                # Expenses - own only (enforced at view level)
                ("expenses", "expensereport", "view_expensereport"),
                ("expenses", "expensereport", "add_expensereport"),
                ("expenses", "expensereport", "change_expensereport"),
                ("expenses", "expenseitem", "view_expenseitem"),
                ("expenses", "expenseitem", "add_expenseitem"),
                ("expenses", "expenseitem", "change_expenseitem"),
                ("expenses", "expenseitem", "delete_expenseitem"),
                ("expenses", "expensereceipt", "view_expensereceipt"),
                ("expenses", "expensereceipt", "add_expensereceipt"),
                ("expenses", "expensereceipt", "delete_expensereceipt"),
                ("expenses", "mileageentry", "view_mileageentry"),
                ("expenses", "mileageentry", "add_mileageentry"),
                ("expenses", "mileageentry", "change_mileageentry"),
                ("expenses", "mileageentry", "delete_mileageentry"),
                ("expenses", "expensecategory", "view_expensecategory"),
            ],
            "office_manager": [
                # Full access to timesheets
                ("timesheets", "timesheet", "view_timesheet"),
                ("timesheets", "timesheet", "add_timesheet"),
                ("timesheets", "timesheet", "change_timesheet"),
                ("timesheets", "timesheetline", "view_timesheetline"),
                ("timesheets", "timesheetline", "add_timesheetline"),
                ("timesheets", "timesheetline", "change_timesheetline"),
                ("timesheets", "timesheetline", "delete_timesheetline"),
                ("timesheets", "timeentry", "view_timeentry"),
                ("timesheets", "timeentry", "add_timeentry"),
                ("timesheets", "timeentry", "change_timeentry"),
                ("timesheets", "timeentry", "delete_timeentry"),
                ("timesheets", "chargecode", "view_chargecode"),
                ("timesheets", "chargecode", "add_chargecode"),
                ("timesheets", "chargecode", "change_chargecode"),
                # Full access to expenses
                ("expenses", "expensereport", "view_expensereport"),
                ("expenses", "expensereport", "add_expensereport"),
                ("expenses", "expensereport", "change_expensereport"),
                ("expenses", "expenseitem", "view_expenseitem"),
                ("expenses", "expenseitem", "add_expenseitem"),
                ("expenses", "expenseitem", "change_expenseitem"),
                ("expenses", "expenseitem", "delete_expenseitem"),
                ("expenses", "expensereceipt", "view_expensereceipt"),
                ("expenses", "expensereceipt", "add_expensereceipt"),
                ("expenses", "expensereceipt", "delete_expensereceipt"),
                ("expenses", "mileageentry", "view_mileageentry"),
                ("expenses", "mileageentry", "add_mileageentry"),
                ("expenses", "mileageentry", "change_mileageentry"),
                ("expenses", "mileageentry", "delete_mileageentry"),
                ("expenses", "expensecategory", "view_expensecategory"),
                ("expenses", "expensecategory", "add_expensecategory"),
                ("expenses", "expensecategory", "change_expensecategory"),
                # Periods management
                ("periods", "timesheetperiod", "view_timesheetperiod"),
                ("periods", "timesheetperiod", "add_timesheetperiod"),
                ("periods", "timesheetperiod", "change_timesheetperiod"),
                ("periods", "expensemonth", "view_expensemonth"),
                ("periods", "expensemonth", "add_expensemonth"),
                ("periods", "expensemonth", "change_expensemonth"),
                # Reviews
                ("reviews", "reviewaction", "view_reviewaction"),
                ("reviews", "reviewaction", "add_reviewaction"),
                ("reviews", "reviewcomment", "view_reviewcomment"),
                ("reviews", "reviewcomment", "add_reviewcomment"),
                ("reviews", "reviewcomment", "change_reviewcomment"),
                # Exports
                ("exports", "exportjob", "view_exportjob"),
                ("exports", "exportjob", "add_exportjob"),
                ("exports", "exportdownload", "view_exportdownload"),
                # User/Employee management (view only)
                ("accounts", "user", "view_user"),
                ("accounts", "employeeprofile", "view_employeeprofile"),
                ("accounts", "employeeprofile", "change_employeeprofile"),
            ],
            "managing_partner": [
                # Read-only access to everything
                ("timesheets", "timesheet", "view_timesheet"),
                ("timesheets", "timesheetline", "view_timesheetline"),
                ("timesheets", "timeentry", "view_timeentry"),
                ("timesheets", "chargecode", "view_chargecode"),
                ("expenses", "expensereport", "view_expensereport"),
                ("expenses", "expenseitem", "view_expenseitem"),
                ("expenses", "expensereceipt", "view_expensereceipt"),
                ("expenses", "mileageentry", "view_mileageentry"),
                ("expenses", "expensecategory", "view_expensecategory"),
                ("exports", "exportjob", "view_exportjob"),
                ("exports", "exportdownload", "view_exportdownload"),
            ],
            "payroll_partner": [
                # Read-only + download exports
                ("timesheets", "timesheet", "view_timesheet"),
                ("expenses", "expensereport", "view_expensereport"),
                ("exports", "exportjob", "view_exportjob"),
                ("exports", "exportdownload", "view_exportdownload"),
            ],
            "accountants": [
                # Read-only + download exports
                ("expenses", "expensereport", "view_expensereport"),
                ("expenses", "expenseitem", "view_expenseitem"),
                ("expenses", "expensereceipt", "view_expensereceipt"),
                ("expenses", "mileageentry", "view_mileageentry"),
                ("exports", "exportjob", "view_exportjob"),
                ("exports", "exportdownload", "view_exportdownload"),
            ],
        }

        for group_name, permissions in role_permissions.items():
            group, created = Group.objects.get_or_create(name=group_name)
            action = "Created" if created else "Updated"

            # Clear existing permissions and set new ones
            group.permissions.clear()

            for app_label, model, codename in permissions:
                try:
                    ct = ContentType.objects.get(app_label=app_label, model=model)
                    perm = Permission.objects.get(content_type=ct, codename=codename)
                    group.permissions.add(perm)
                except (ContentType.DoesNotExist, Permission.DoesNotExist):
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Permission {app_label}.{codename} not found (model may not exist yet)"
                        )
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} group '{group_name}' with {group.permissions.count()} permissions"
                )
            )

        self.stdout.write(self.style.SUCCESS("\nRole groups configured successfully!"))
