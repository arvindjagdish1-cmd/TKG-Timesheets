import os
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


def receipt_upload_path(instance, filename):
    """Generate unique path for uploaded receipts."""
    ext = os.path.splitext(filename)[1]
    month = instance.expense_item.report.month
    return f"receipts/{month.year}/{month.month:02d}/{uuid4().hex}{ext}"


class ExpenseCategory(models.Model):
    """
    Categories for expense items.
    Maps to columns in the export template.
    """

    name = models.CharField("name", max_length=100, unique=True)
    active = models.BooleanField("active", default=True)

    # Template mapping for XLSX export
    template_sheet = models.CharField(
        "template sheet",
        max_length=50,
        default="Expenses-Main",
        help_text="Sheet name in the export template.",
    )
    template_column = models.CharField(
        "template column",
        max_length=5,
        blank=True,
        help_text="Column letter in the export template.",
    )

    # Validation rules
    requires_client = models.BooleanField(
        "requires client",
        default=False,
        help_text="If true, a client name is required for this category.",
    )
    receipt_required_threshold = models.DecimalField(
        "receipt threshold",
        max_digits=10,
        decimal_places=2,
        default=Decimal("20.00"),
        help_text="Amounts above this require a receipt or paper receipt flag.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "expense category"
        verbose_name_plural = "expense categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ExpenseReport(models.Model):
    """
    A monthly expense report for an employee.
    Contains expense items and mileage entries.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        RETURNED = "RETURNED", "Returned"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expense_reports",
    )
    month = models.ForeignKey(
        "periods.ExpenseMonth",
        on_delete=models.PROTECT,
        related_name="expense_reports",
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
        related_name="approved_expense_reports",
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
        verbose_name = "expense report"
        verbose_name_plural = "expense reports"
        ordering = ["-month__year", "-month__month", "employee__email"]
        unique_together = [("employee", "month")]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.month}"

    @property
    def is_editable(self):
        """Report can be edited if draft or returned, and month is not locked."""
        return (
            self.status in (self.Status.DRAFT, self.Status.RETURNED)
            and not self.month.is_locked
        )

    @property
    def total_expenses(self):
        """Sum of all expense items."""
        return sum(item.amount for item in self.items.all())

    @property
    def total_mileage_amount(self):
        """Sum of all mileage reimbursements."""
        return sum(entry.total_amount for entry in self.mileage_entries.all())

    @property
    def grand_total(self):
        """Total expenses + mileage."""
        return self.total_expenses + self.total_mileage_amount

    def submit(self):
        """Submit the expense report for review."""
        if not self.is_editable:
            raise ValidationError("Expense report cannot be submitted in its current state.")
        self.status = self.Status.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "updated_at"])

    def approve(self, approver):
        """Approve the expense report."""
        if self.status != self.Status.SUBMITTED:
            raise ValidationError("Only submitted expense reports can be approved.")
        self.status = self.Status.APPROVED
        self.approved_at = timezone.now()
        self.approved_by = approver
        self.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])

    def return_for_revision(self, notes=""):
        """Return the report to the employee for revision."""
        if self.status != self.Status.SUBMITTED:
            raise ValidationError("Only submitted expense reports can be returned.")
        self.status = self.Status.RETURNED
        if notes:
            self.reviewer_notes = notes
        self.save(update_fields=["status", "reviewer_notes", "updated_at"])


class ExpenseItem(models.Model):
    """
    A single expense item in an expense report.
    """

    report = models.ForeignKey(
        ExpenseReport,
        on_delete=models.CASCADE,
        related_name="items",
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expense_items",
    )

    date = models.DateField("date")
    amount = models.DecimalField(
        "amount",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    description = models.CharField("description", max_length=300)

    # Optional client/vendor info
    client = models.CharField(
        "client/vendor",
        max_length=200,
        blank=True,
        help_text="Client or vendor name, if applicable.",
    )

    # Receipt handling
    paper_receipt_delivered = models.BooleanField(
        "paper receipt delivered",
        default=False,
        help_text="Check if paper receipt was delivered to office manager.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "expense item"
        verbose_name_plural = "expense items"
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.date}: {self.category.name} - ${self.amount}"

    @property
    def requires_receipt(self):
        """Check if this expense requires a receipt based on amount threshold."""
        threshold = self.category.receipt_required_threshold
        return self.amount > threshold

    @property
    def has_receipt(self):
        """Check if at least one receipt is attached."""
        return self.receipts.exists()

    @property
    def receipt_requirement_met(self):
        """Check if receipt requirement is satisfied."""
        if not self.requires_receipt:
            return True
        return self.has_receipt or self.paper_receipt_delivered

    def clean(self):
        """Validate the expense item."""
        errors = {}

        # Check date is within the expense month
        if self.report:
            month = self.report.month
            if not (month.start_date <= self.date <= month.end_date):
                errors["date"] = f"Date must be within {month.display_name}."

        # Check client requirement
        if self.category and self.category.requires_client and not self.client:
            errors["client"] = "This category requires a client/vendor name."

        if errors:
            raise ValidationError(errors)


class ExpenseReceipt(models.Model):
    """
    A receipt attachment for an expense item.
    Multiple receipts can be attached to a single expense.
    """

    expense_item = models.ForeignKey(
        ExpenseItem,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    file = models.FileField("receipt file", upload_to=receipt_upload_path)
    original_filename = models.CharField("original filename", max_length=255)
    uploaded_at = models.DateTimeField("uploaded at", auto_now_add=True)

    class Meta:
        verbose_name = "expense receipt"
        verbose_name_plural = "expense receipts"
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"Receipt for {self.expense_item}"

    def save(self, *args, **kwargs):
        if not self.original_filename and self.file:
            self.original_filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)


class MileageEntry(models.Model):
    """
    A mileage reimbursement entry in an expense report.
    """

    report = models.ForeignKey(
        ExpenseReport,
        on_delete=models.CASCADE,
        related_name="mileage_entries",
    )
    date = models.DateField("date")
    miles = models.DecimalField(
        "miles",
        max_digits=7,
        decimal_places=1,
        validators=[MinValueValidator(Decimal("0.1"))],
    )
    description = models.CharField(
        "description",
        max_length=300,
        help_text="Purpose and destinations (e.g., 'Client meeting: Office -> ABC Corp -> Office').",
    )

    # Rate can be overridden per entry if needed, or pulled from employee profile
    rate_override = models.DecimalField(
        "rate override ($/mile)",
        max_digits=5,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Leave blank to use employee's default rate.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "mileage entry"
        verbose_name_plural = "mileage entries"
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.date}: {self.miles} miles"

    @property
    def rate(self):
        """Get the applicable rate for this entry."""
        if self.rate_override:
            return self.rate_override
        # Try to get from employee profile
        try:
            return self.report.employee.profile.mileage_rate
        except Exception:
            return Decimal("0.67")  # IRS default

    @property
    def total_amount(self):
        """Calculate reimbursement amount."""
        return self.miles * self.rate

    def clean(self):
        """Validate the mileage entry."""
        if self.report:
            month = self.report.month
            if not (month.start_date <= self.date <= month.end_date):
                raise ValidationError(
                    {"date": f"Date must be within {month.display_name}."}
                )
