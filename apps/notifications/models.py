from django.conf import settings
from django.db import models


class NotificationLog(models.Model):
    """
    Log of sent notifications (emails, reminders).
    """

    class NotificationType(models.TextChoices):
        TIMESHEET_REMINDER = "TS_REMINDER", "Timesheet Reminder"
        EXPENSE_REMINDER = "EX_REMINDER", "Expense Reminder"
        SUBMISSION_CONFIRM = "SUBMIT_CONFIRM", "Submission Confirmation"
        APPROVAL_NOTIFY = "APPROVAL", "Approval Notification"
        RETURN_NOTIFY = "RETURN", "Return Notification"

    notification_type = models.CharField(
        "type",
        max_length=20,
        choices=NotificationType.choices,
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    subject = models.CharField("subject", max_length=255)
    body = models.TextField("body")

    # Delivery status
    sent_at = models.DateTimeField("sent at", null=True, blank=True)
    error_message = models.TextField("error", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notification log"
        verbose_name_plural = "notification logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_notification_type_display()} to {self.recipient.email}"
