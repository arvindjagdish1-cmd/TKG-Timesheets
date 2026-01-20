import calendar
from datetime import date

from django.core.management.base import BaseCommand

from apps.periods.models import TimesheetPeriod, ExpenseMonth


class Command(BaseCommand):
    help = "Create timesheet periods (half-months) and expense month for a given year/month."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True, help="Year (YYYY)")
        parser.add_argument("--month", type=int, required=True, help="Month (1-12)")
        parser.add_argument(
            "--due-offset",
            type=int,
            default=3,
            help="Days after period end for due date (default: 3)",
        )
        parser.add_argument(
            "--reminder-offset",
            type=int,
            default=2,
            help="Days before due date for reminder (default: 2)",
        )

    def handle(self, *args, **options):
        year = options["year"]
        month = options["month"]
        due_offset = options["due_offset"]
        reminder_offset = options["reminder_offset"]

        if not 1 <= month <= 12:
            self.stderr.write(self.style.ERROR("Month must be between 1 and 12."))
            return

        _, last_day = calendar.monthrange(year, month)

        # First half: 1st - 15th
        first_start = date(year, month, 1)
        first_end = date(year, month, 15)
        first_due = date(year, month, 15 + due_offset)
        first_reminder = date(year, month, 15 + due_offset - reminder_offset)

        # Handle month boundary for due dates
        if first_due.day > last_day:
            # Roll over to next month
            if month == 12:
                first_due = date(year + 1, 1, first_due.day - last_day)
            else:
                first_due = date(year, month + 1, first_due.day - last_day)

        period1, created1 = TimesheetPeriod.objects.update_or_create(
            year=year,
            month=month,
            half=TimesheetPeriod.Half.FIRST,
            defaults={
                "start_date": first_start,
                "end_date": first_end,
                "due_date": first_due,
                "reminder_date": first_reminder,
            },
        )
        action1 = "Created" if created1 else "Updated"
        self.stdout.write(f"{action1}: {period1}")

        # Second half: 16th - end of month
        second_start = date(year, month, 16)
        second_end = date(year, month, last_day)

        # Due date for second half is typically a few days into next month
        if month == 12:
            second_due = date(year + 1, 1, due_offset)
            second_reminder = date(year + 1, 1, max(1, due_offset - reminder_offset))
        else:
            second_due = date(year, month + 1, due_offset)
            second_reminder = date(year, month + 1, max(1, due_offset - reminder_offset))

        period2, created2 = TimesheetPeriod.objects.update_or_create(
            year=year,
            month=month,
            half=TimesheetPeriod.Half.SECOND,
            defaults={
                "start_date": second_start,
                "end_date": second_end,
                "due_date": second_due,
                "reminder_date": second_reminder,
            },
        )
        action2 = "Created" if created2 else "Updated"
        self.stdout.write(f"{action2}: {period2}")

        # Expense month (full month)
        expense_start = date(year, month, 1)
        expense_end = date(year, month, last_day)

        # Expense due date is typically a few days into next month
        if month == 12:
            expense_due = date(year + 1, 1, due_offset + 2)
            expense_reminder = date(year + 1, 1, max(1, due_offset))
        else:
            expense_due = date(year, month + 1, due_offset + 2)
            expense_reminder = date(year, month + 1, max(1, due_offset))

        expense_month, created3 = ExpenseMonth.objects.update_or_create(
            year=year,
            month=month,
            defaults={
                "start_date": expense_start,
                "end_date": expense_end,
                "due_date": expense_due,
                "reminder_date": expense_reminder,
            },
        )
        action3 = "Created" if created3 else "Updated"
        self.stdout.write(f"{action3}: {expense_month}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed periods for {year}-{month:02d}."
            )
        )
