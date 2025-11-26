from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

@shared_task
def send_welcome_email_task(user_id, token):
    from .models import User  # import here to avoid circular imports
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    context = {
        "user": user,
        "token": token,
        "year": timezone.now().year,
    }

    subject = "Welcome! Verify Your Account"
    html_content = render_to_string("emails/welcome_email.html", context)
    text_content = f"Hello {user.first_name},\nYour verification token is: {token}"

    email = EmailMultiAlternatives(
        subject,
        text_content,
        "no-reply@yourdomain.com",
        [user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
