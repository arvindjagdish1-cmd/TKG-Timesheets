import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tkg_te.settings")

app = Celery("tkg_te")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
