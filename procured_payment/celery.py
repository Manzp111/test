import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "procured_payment.settings")

app = Celery("procured_payment")

# Use broker URL from environment
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
