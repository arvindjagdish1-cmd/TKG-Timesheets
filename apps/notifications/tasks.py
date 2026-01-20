"""
Celery tasks for sending notifications and reminders.
"""

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.periods.models import TimesheetPeriod, ExpenseMonth
from apps.timesheets.models import Timesheet
from apps.expenses.models import ExpenseReport
from .models import NotificationLog

User = get_user_model()


@shared_task
def send_timesheet_reminders():
    """
    Send reminders for timesheets due soon.
    Runs via Celery beat, typically 2 days before due date.
    """
    today = timezone.now().date()

    # Find periods where reminder_date is today
    periods = TimesheetPeriod.objects.filter(
        reminder_date=today,
        is_locked=False,
    )

    sent_count = 0
    for period in periods:
        # Find employees who haven't submitted
        pending_timesheets = Timesheet.objects.filter(
            period=period,
            status__in=[Timesheet.Status.DRAFT, Timesheet.Status.RETURNED],
        ).select_related("employee")

        for timesheet in pending_timesheets:
            try:
                send_reminder_email.delay(
                    user_id=timesheet.employee.id,
                    notification_type=NotificationLog.NotificationType.TIMESHEET_REMINDER,
                    subject=f"Reminder: Timesheet due for {period.display_name}",
                    body=f"""
Hi {timesheet.employee.get_short_name()},

This is a friendly reminder that your timesheet for {period.display_name} is due on {period.due_date.strftime('%B %d, %Y')}.

Please log in and submit your timesheet at your earliest convenience.

Thank you,
TKG Time & Expense Portal
                    """.strip(),
                )
                sent_count += 1
            except Exception as e:
                print(f"Error sending reminder to {timesheet.employee.email}: {e}")

    return f"Sent {sent_count} timesheet reminders"


@shared_task
def send_expense_reminders():
    """
    Send reminders for expense reports due soon.
    """
    today = timezone.now().date()

    months = ExpenseMonth.objects.filter(
        reminder_date=today,
        is_locked=False,
    )

    sent_count = 0
    for month in months:
        pending_reports = ExpenseReport.objects.filter(
            month=month,
            status__in=[ExpenseReport.Status.DRAFT, ExpenseReport.Status.RETURNED],
        ).select_related("employee")

        for report in pending_reports:
            try:
                send_reminder_email.delay(
                    user_id=report.employee.id,
                    notification_type=NotificationLog.NotificationType.EXPENSE_REMINDER,
                    subject=f"Reminder: Expense report due for {month.display_name}",
                    body=f"""
Hi {report.employee.get_short_name()},

This is a friendly reminder that your expense report for {month.display_name} is due on {month.due_date.strftime('%B %d, %Y')}.

Please log in and submit your expense report at your earliest convenience.

Thank you,
TKG Time & Expense Portal
                    """.strip(),
                )
                sent_count += 1
            except Exception as e:
                print(f"Error sending reminder to {report.employee.email}: {e}")

    return f"Sent {sent_count} expense reminders"


@shared_task
def send_reminder_email(user_id, notification_type, subject, body):
    """
    Send an email notification to a user.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return "User not found"

    # Create log entry
    log = NotificationLog.objects.create(
        notification_type=notification_type,
        recipient=user,
        subject=subject,
        body=body,
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        log.sent_at = timezone.now()
        log.save(update_fields=["sent_at"])
        return f"Email sent to {user.email}"
    except Exception as e:
        log.error_message = str(e)
        log.save(update_fields=["error_message"])
        raise


@shared_task
def auto_create_employee_records():
    """
    Automatically create Timesheet and ExpenseReport records for active employees
    when new periods are created.
    """
    current_ts_period = TimesheetPeriod.get_current_period()
    current_expense_month = ExpenseMonth.get_current_month()

    if not current_ts_period and not current_expense_month:
        return "No active periods found"

    # Get active employees
    active_employees = User.objects.filter(
        is_active=True,
        groups__name="employees"
    ).distinct()

    ts_created = 0
    er_created = 0

    for employee in active_employees:
        # Create timesheet if period exists
        if current_ts_period:
            _, created = Timesheet.objects.get_or_create(
                employee=employee,
                period=current_ts_period,
            )
            if created:
                ts_created += 1

        # Create expense report if month exists
        if current_expense_month:
            _, created = ExpenseReport.objects.get_or_create(
                employee=employee,
                month=current_expense_month,
            )
            if created:
                er_created += 1

    return f"Created {ts_created} timesheets and {er_created} expense reports"


@shared_task
def send_submission_confirmation(user_id, submission_type, period_name):
    """
    Send confirmation email after successful submission.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return "User not found"

    subject = f"Submission Confirmed: {submission_type} for {period_name}"
    body = f"""
Hi {user.get_short_name()},

Your {submission_type.lower()} for {period_name} has been successfully submitted for review.

You will receive another notification once it has been reviewed.

Thank you,
TKG Time & Expense Portal
    """.strip()

    return send_reminder_email(
        user_id=user_id,
        notification_type=NotificationLog.NotificationType.SUBMISSION_CONFIRM,
        subject=subject,
        body=body,
    )


@shared_task
def send_approval_notification(user_id, submission_type, period_name, approved_by):
    """
    Send notification when submission is approved.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return "User not found"

    subject = f"Approved: {submission_type} for {period_name}"
    body = f"""
Hi {user.get_short_name()},

Good news! Your {submission_type.lower()} for {period_name} has been approved by {approved_by}.

Thank you,
TKG Time & Expense Portal
    """.strip()

    return send_reminder_email(
        user_id=user_id,
        notification_type=NotificationLog.NotificationType.APPROVAL_NOTIFY,
        subject=subject,
        body=body,
    )


@shared_task
def send_return_notification(user_id, submission_type, period_name, reason):
    """
    Send notification when submission is returned for revision.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return "User not found"

    subject = f"Action Required: {submission_type} for {period_name}"
    body = f"""
Hi {user.get_short_name()},

Your {submission_type.lower()} for {period_name} has been returned for revision.

Reason: {reason}

Please log in, make the necessary corrections, and resubmit.

Thank you,
TKG Time & Expense Portal
    """.strip()

    return send_reminder_email(
        user_id=user_id,
        notification_type=NotificationLog.NotificationType.RETURN_NOTIFY,
        subject=subject,
        body=body,
    )
