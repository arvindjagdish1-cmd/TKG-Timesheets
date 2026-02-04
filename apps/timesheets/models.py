from decimal import Decimal
import hashlib
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class ChargeCode(models.Model):
    """
    Charge codes for categorizing time entries.
    Examples: ADM (Admin), CHI-MID (Chicago Mid-Market), PTO (Personal Time), etc.
    """

    code = models.CharField("code", max_length=20, unique=True)
    description = models.CharField("description", max_length=200)
    active = models.BooleanField("active", default=True)

    # Optional: link to client/project if needed
    is_client_work = models.BooleanField(
        "client work",
        default=False,
        help_text="If true, may require additional fields like client name.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "charge code"
        verbose_name_plural = "charge codes"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.description}"


class ClientMapping(models.Model):
    code = models.CharField("charge code", max_length=50, unique=True)
    display_name = models.CharField("display name", max_length=200)
    sort_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "display_name"]
        verbose_name = "client mapping"
        verbose_name_plural = "client mappings"

    def __str__(self):
        return f"{self.code} - {self.display_name}"


def timesheet_upload_path(instance, filename):
    ext = filename.split(".")[-1].lower() if "." in filename else "xlsx"
    return (
        f"timesheet_uploads/{instance.year}/{instance.month:02d}/"
        f"{instance.user_id}/{uuid.uuid4().hex}.{ext}"
    )


class TimesheetUpload(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        RETURNED = "RETURNED", "Returned"
        APPROVED = "APPROVED", "Approved"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timesheet_uploads",
    )
    uploaded_file = models.FileField(upload_to=timesheet_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    sha256 = models.CharField(max_length=64, blank=True)

    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    parsed_json = models.JSONField(default=dict, blank=True)
    errors_json = models.JSONField(default=list, blank=True)
    has_blocking_errors = models.BooleanField(default=False)
    source_template_version = models.CharField(max_length=100, blank=True)
    reviewer_comment = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_uploads",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month", "-uploaded_at"]
        indexes = [
            models.Index(fields=["user", "year", "month"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} {self.year}-{self.month:02d}"

    def set_sha256_from_bytes(self, file_bytes):
        self.sha256 = hashlib.sha256(file_bytes).hexdigest()


class Timesheet(models.Model):
    """
    A timesheet for an employee for a specific half-month period.
    Contains multiple TimesheetLines, each with daily time entries.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        RETURNED = "RETURNED", "Returned"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timesheets",
    )
    period = models.ForeignKey(
        "periods.TimesheetPeriod",
        on_delete=models.PROTECT,
        related_name="timesheets",
    )

    status = models.CharField(
        "status",
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    # Submission tracking
    submitted_at = models.DateTimeField("submitted at", null=True, blank=True)
    approved_at = models.DateTimeField("approved at", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_timesheets",
    )

    # Notes
    employee_notes = models.TextField(
        "employee notes",
        blank=True,
        help_text="Notes from employee to reviewer.",
    )
    reviewer_notes = models.TextField(
        "reviewer notes",
        blank=True,
        help_text="Notes from reviewer to employee.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "timesheet"
        verbose_name_plural = "timesheets"
        ordering = ["-period__year", "-period__month", "employee__email"]
        unique_together = [("employee", "period")]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.period}"

    @property
    def is_editable(self):
        """Timesheet can be edited if draft or returned, and period is not locked."""
        return (
            self.status in (self.Status.DRAFT, self.Status.RETURNED)
            and not self.period.is_locked
        )

    @property
    def total_hours(self):
        """Sum of all time entries in this timesheet."""
        total = Decimal("0")
        for line in self.lines.all():
            total += line.total_hours
        return total

    def submit(self):
        """Submit the timesheet for review."""
        if not self.is_editable:
            raise ValidationError("Timesheet cannot be submitted in its current state.")
        self.status = self.Status.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "updated_at"])

    def approve(self, approver):
        """Approve the timesheet."""
        if self.status != self.Status.SUBMITTED:
            raise ValidationError("Only submitted timesheets can be approved.")
        self.status = self.Status.APPROVED
        self.approved_at = timezone.now()
        self.approved_by = approver
        self.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])

    def return_for_revision(self, notes=""):
        """Return the timesheet to the employee for revision."""
        if self.status != self.Status.SUBMITTED:
            raise ValidationError("Only submitted timesheets can be returned.")
        self.status = self.Status.RETURNED
        if notes:
            self.reviewer_notes = notes
        self.save(update_fields=["status", "reviewer_notes", "updated_at"])


class TimesheetLine(models.Model):
    """
    A single line on a timesheet, representing one charge code.
    Contains daily entries for each day in the period.
    """

    timesheet = models.ForeignKey(
        Timesheet,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    charge_code = models.ForeignKey(
        ChargeCode,
        on_delete=models.PROTECT,
        related_name="timesheet_lines",
    )

    # Optional label for client work
    label = models.CharField(
        "label/description",
        max_length=200,
        blank=True,
        help_text="Description or client name for this line.",
    )

    # Order for display
    order = models.PositiveSmallIntegerField("display order", default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "timesheet line"
        verbose_name_plural = "timesheet lines"
        ordering = ["order", "id"]
        unique_together = [("timesheet", "charge_code", "label")]

    def __str__(self):
        label_part = f" ({self.label})" if self.label else ""
        return f"{self.charge_code.code}{label_part}"

    @property
    def total_hours(self):
        """Sum of all daily entries for this line."""
        return sum(entry.hours for entry in self.entries.all())

    def clean(self):
        """Validate that client work has a label."""
        if self.charge_code and self.charge_code.is_client_work and not self.label:
            raise ValidationError(
                {"label": "Client work charge codes require a description/label."}
            )


class TimeEntry(models.Model):
    """
    A single time entry for one day on a timesheet line.
    Hours are stored as decimal to support quarter-hour increments.
    """

    line = models.ForeignKey(
        TimesheetLine,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    date = models.DateField("date")
    hours = models.DecimalField(
        "hours",
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("24.00")),
        ],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "time entry"
        verbose_name_plural = "time entries"
        ordering = ["date"]
        unique_together = [("line", "date")]

    def __str__(self):
        return f"{self.date}: {self.hours}h"

    def clean(self):
        """Validate hours increment and date within period."""
        # Check quarter-hour increments
        increment_minutes = getattr(settings, "TIME_INCREMENT_MINUTES", 15)
        increment = Decimal(str(increment_minutes)) / Decimal("60")
        if self.hours % increment != 0:
            raise ValidationError(
                {"hours": f"Hours must be in {increment_minutes}-minute increments."}
            )

        # Check date is within the timesheet period
        if self.line and self.line.timesheet:
            period = self.line.timesheet.period
            if not (period.start_date <= self.date <= period.end_date):
                raise ValidationError(
                    {"date": f"Date must be within the period ({period.start_date} to {period.end_date})."}
                )
