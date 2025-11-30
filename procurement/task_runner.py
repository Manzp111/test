# myapp/tasks_runner.py
import threading
import logging
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.db import transaction
from django.conf import settings
from weasyprint import HTML
from time import sleep

from .models import PurchaseRequest
from .document_processing import extract_text_from_any_pdf, parse_with_ai
from .ai_matching import are_items_same

logger = logging.getLogger(__name__)

def run_in_background(func, *args, **kwargs):
    """Run a function in a separate daemon thread"""
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
