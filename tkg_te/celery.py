import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tkg_te.settings")

app = Celery("tkg_te")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    # Send timesheet reminders daily at 9 AM
    "send-timesheet-reminders": {
        "task": "apps.notifications.tasks.send_timesheet_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    # Send expense reminders daily at 9 AM
    "send-expense-reminders": {
        "task": "apps.notifications.tasks.send_expense_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    # Auto-create records for new periods (runs at midnight on the 1st and 16th)
    "auto-create-records": {
        "task": "apps.notifications.tasks.auto_create_employee_records",
        "schedule": crontab(hour=0, minute=5, day_of_month="1,16"),
    },
}

app.conf.timezone = "America/Chicago"
