import os
from uuid import uuid4

from django.conf import settings
from django.db import models


def export_upload_path(instance, filename):
    """Generate path for export files."""
    ext = os.path.splitext(filename)[1]
    return f"exports/{instance.export_type}/{uuid4().hex}{ext}"


class ExportJob(models.Model):
    """
    Tracks export generation jobs.
    Can be XLSX, PDF, or bundled ZIP files.
    """

    class ExportType(models.TextChoices):
        TIMESHEET_XLSX = "TS_XLSX", "Timesheet XLSX"
        TIMESHEET_PDF = "TS_PDF", "Timesheet PDF"
        EXPENSE_XLSX = "EX_XLSX", "Expense XLSX"
        EXPENSE_PDF = "EX_PDF", "Expense PDF"
        TIMESHEET_PACK = "TS_PACK", "Timesheet PDF Pack"
        EXPENSE_PACK_SENIORITY = "EX_PACK_S", "Expense PDF Pack (Seniority)"
        EXPENSE_PACK_ALPHA = "EX_PACK_A", "Expense PDF Pack (Alphabetical)"
        ZIP_BUNDLE = "ZIP", "ZIP Bundle"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    export_type = models.CharField(
        "export type",
        max_length=15,
        choices=ExportType.choices,
    )
    status = models.CharField(
        "status",
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Scope
    year = models.PositiveIntegerField("year")
    month = models.PositiveSmallIntegerField("month")
    half = models.CharField(
        "half",
        max_length=6,
        blank=True,
        help_text="For timesheet exports: FIRST or SECOND",
    )

    # Optional link to specific employee (for individual exports)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exports",
    )

    # Output
    file = models.FileField(
        "export file",
        upload_to=export_upload_path,
        null=True,
        blank=True,
    )
    filename = models.CharField("filename", max_length=255, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_exports",
    )
    error_message = models.TextField("error message", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField("completed at", null=True, blank=True)

    class Meta:
        verbose_name = "export job"
        verbose_name_plural = "export jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_export_type_display()} - {self.year}-{self.month:02d}"

    @property
    def is_complete(self):
        return self.status == self.Status.COMPLETED

    @property
    def is_failed(self):
        return self.status == self.Status.FAILED


class ExportDownload(models.Model):
    """
    Audit log of who downloaded which exports.
    """

    export = models.ForeignKey(
        ExportJob,
        on_delete=models.CASCADE,
        related_name="downloads",
    )
    downloaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="export_downloads",
    )
    downloaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField("IP address", null=True, blank=True)
    user_agent = models.CharField("user agent", max_length=500, blank=True)

    class Meta:
        verbose_name = "export download"
        verbose_name_plural = "export downloads"
        ordering = ["-downloaded_at"]

    def __str__(self):
        return f"{self.downloaded_by.email} downloaded {self.export.filename}"
