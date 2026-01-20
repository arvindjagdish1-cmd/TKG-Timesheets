from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ReviewAction(models.Model):
    """
    Records actions taken during the review process.
    Can be linked to Timesheet or ExpenseReport.
    """

    class ActionType(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        RETURNED = "RETURNED", "Returned"
        RESUBMITTED = "RESUBMITTED", "Re-submitted"
        COMMENT = "COMMENT", "Comment"

    # Generic foreign key to link to Timesheet or ExpenseReport
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    action = models.CharField(
        "action",
        max_length=15,
        choices=ActionType.choices,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_actions",
    )
    comment = models.TextField("comment", blank=True)
    created_at = models.DateTimeField("created at", auto_now_add=True)

    class Meta:
        verbose_name = "review action"
        verbose_name_plural = "review actions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor.get_full_name()} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def log_action(cls, obj, action, actor, comment=""):
        """Helper to create a review action for any reviewable object."""
        ct = ContentType.objects.get_for_model(obj)
        return cls.objects.create(
            content_type=ct,
            object_id=obj.pk,
            action=action,
            actor=actor,
            comment=comment,
        )


class ReviewComment(models.Model):
    """
    Comments attached to timesheets or expense reports during review.
    Separate from actions for richer discussion threads.
    """

    # Generic foreign key to link to Timesheet or ExpenseReport
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_comments",
    )
    text = models.TextField("comment")
    is_internal = models.BooleanField(
        "internal only",
        default=False,
        help_text="If true, only visible to office managers/reviewers.",
    )
    created_at = models.DateTimeField("created at", auto_now_add=True)
    updated_at = models.DateTimeField("updated at", auto_now=True)

    class Meta:
        verbose_name = "review comment"
        verbose_name_plural = "review comments"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        truncated = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"{self.author.get_short_name()}: {truncated}"
