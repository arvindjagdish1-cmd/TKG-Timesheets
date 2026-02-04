from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from simple_history.models import HistoricalRecords


class TimesheetPeriod(models.Model):
    """
    Represents a half-month timesheet period.
    First half: 1st - 15th
    Second half: 16th - last day of month
    """

    class Half(models.TextChoices):
        FIRST = "FIRST", "1st – 15th"
        SECOND = "SECOND", "16th – End"

    year = models.PositiveIntegerField("year")
    month = models.PositiveSmallIntegerField("month")  # 1-12
    half = models.CharField("half", max_length=6, choices=Half.choices)

    start_date = models.DateField("start date")
    end_date = models.DateField("end date")

    # Submission deadlines
    due_date = models.DateField(
        "due date",
        help_text="Date by which timesheets must be submitted.",
    )
    reminder_date = models.DateField(
        "reminder date",
        null=True,
        blank=True,
        help_text="Date to send reminder emails (typically 2 days before due).",
    )

    # Status
    is_locked = models.BooleanField(
        "locked",
        default=False,
        help_text="If locked, no more edits are allowed.",
    )
    locked_at = models.DateTimeField("locked at", null=True, blank=True)
    locked_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locked_timesheet_periods",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "timesheet period"
        verbose_name_plural = "timesheet periods"
        ordering = ["-year", "-month", "-half"]
        unique_together = [("year", "month", "half")]

    def __str__(self):
        half_label = "1st-15th" if self.half == self.Half.FIRST else "16th-End"
        return f"{self.year}-{self.month:02d} ({half_label})"

    @property
    def display_name(self):
        """Human-readable period name."""
        from calendar import month_abbr

        half_label = "1st-15th" if self.half == self.Half.FIRST else "16th-End"
        return f"{month_abbr[self.month]} {self.year} ({half_label})"

    @property
    def is_past_due(self):
        return timezone.now().date() > self.due_date

    @property
    def is_current(self):
        """Check if today falls within this period."""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    def lock(self, user=None):
        """Lock the period to prevent further edits."""
        self.is_locked = True
        self.locked_at = timezone.now()
        self.locked_by = user
        self.save(update_fields=["is_locked", "locked_at", "locked_by"])

    def unlock(self):
        """Unlock the period to allow edits."""
        self.is_locked = False
        self.locked_at = None
        self.locked_by = None
        self.save(update_fields=["is_locked", "locked_at", "locked_by"])

    @classmethod
    def get_current_period(cls):
        """Get the period for today's date."""
        today = timezone.now().date()
        day = today.day
        half = cls.Half.FIRST if day <= 15 else cls.Half.SECOND
        cls.ensure_month(today.year, today.month)
        return cls.objects.filter(year=today.year, month=today.month, half=half).first()

    @classmethod
    def ensure_month(cls, year, month, due_offset=3, reminder_offset=2):
        """Ensure both half-month periods and expense month exist."""
        from calendar import monthrange
        from datetime import date

        last_day = monthrange(year, month)[1]

        first_start = date(year, month, 1)
        first_end = date(year, month, 15)
        first_due = date(year, month, 15 + due_offset)
        first_reminder = date(year, month, 15 + due_offset - reminder_offset)

        if first_due.day > last_day:
            if month == 12:
                first_due = date(year + 1, 1, first_due.day - last_day)
            else:
                first_due = date(year, month + 1, first_due.day - last_day)

        cls.objects.get_or_create(
            year=year,
            month=month,
            half=cls.Half.FIRST,
            defaults={
                "start_date": first_start,
                "end_date": first_end,
                "due_date": first_due,
                "reminder_date": first_reminder,
            },
        )

        second_start = date(year, month, 16)
        second_end = date(year, month, last_day)
        if month == 12:
            second_due = date(year + 1, 1, due_offset)
            second_reminder = date(year + 1, 1, max(1, due_offset - reminder_offset))
        else:
            second_due = date(year, month + 1, due_offset)
            second_reminder = date(year, month + 1, max(1, due_offset - reminder_offset))

        cls.objects.get_or_create(
            year=year,
            month=month,
            half=cls.Half.SECOND,
            defaults={
                "start_date": second_start,
                "end_date": second_end,
                "due_date": second_due,
                "reminder_date": second_reminder,
            },
        )

        ExpenseMonth.ensure_month(year, month, due_offset=due_offset)


class ExpenseMonth(models.Model):
    """
    Represents a monthly expense reporting period.
    Expenses are tracked monthly, while timesheets are half-monthly.
    """

    year = models.PositiveIntegerField("year")
    month = models.PositiveSmallIntegerField("month")  # 1-12

    start_date = models.DateField("start date")
    end_date = models.DateField("end date")

    # Submission deadlines
    due_date = models.DateField(
        "due date",
        help_text="Date by which expense reports must be submitted.",
    )
    reminder_date = models.DateField(
        "reminder date",
        null=True,
        blank=True,
        help_text="Date to send reminder emails.",
    )

    # Status
    is_locked = models.BooleanField(
        "locked",
        default=False,
        help_text="If locked, no more edits are allowed.",
    )
    locked_at = models.DateTimeField("locked at", null=True, blank=True)
    locked_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locked_expense_months",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "expense month"
        verbose_name_plural = "expense months"
        ordering = ["-year", "-month"]
        unique_together = [("year", "month")]

    def __str__(self):
        from calendar import month_abbr

        return f"{month_abbr[self.month]} {self.year}"

    @property
    def display_name(self):
        from calendar import month_name

        return f"{month_name[self.month]} {self.year}"

    @property
    def is_past_due(self):
        return timezone.now().date() > self.due_date

    @property
    def is_current(self):
        """Check if today falls within this month."""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    def lock(self, user=None):
        """Lock the period to prevent further edits."""
        self.is_locked = True
        self.locked_at = timezone.now()
        self.locked_by = user
        self.save(update_fields=["is_locked", "locked_at", "locked_by"])

    def unlock(self):
        """Unlock the period to allow edits."""
        self.is_locked = False
        self.locked_at = None
        self.locked_by = None
        self.save(update_fields=["is_locked", "locked_at", "locked_by"])

    @classmethod
    def get_current_month(cls):
        """Get the expense month for today's date."""
        today = timezone.now().date()
        cls.ensure_month(today.year, today.month)
        return cls.objects.filter(year=today.year, month=today.month).first()

    @classmethod
    def ensure_month(cls, year, month, due_offset=3):
        from calendar import monthrange
        from datetime import date

        last_day = monthrange(year, month)[1]
        expense_start = date(year, month, 1)
        expense_end = date(year, month, last_day)

        if month == 12:
            expense_due = date(year + 1, 1, due_offset + 2)
            expense_reminder = date(year + 1, 1, max(1, due_offset))
        else:
            expense_due = date(year, month + 1, due_offset + 2)
            expense_reminder = date(year, month + 1, max(1, due_offset))

        cls.objects.get_or_create(
            year=year,
            month=month,
            defaults={
                "start_date": expense_start,
                "end_date": expense_end,
                "due_date": expense_due,
                "reminder_date": expense_reminder,
            },
        )

    @property
    def first_timesheet_period(self):
        """Return the first-half timesheet period for this month."""
        return TimesheetPeriod.objects.filter(
            year=self.year, month=self.month, half=TimesheetPeriod.Half.FIRST
        ).first()

    @property
    def second_timesheet_period(self):
        """Return the second-half timesheet period for this month."""
        return TimesheetPeriod.objects.filter(
            year=self.year, month=self.month, half=TimesheetPeriod.Half.SECOND
        ).first()
