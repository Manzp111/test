# users/task.py
import resend

# Direct API key
resend.api_key = "re_D1fTNEDG_8MyXm73aga5gUZPEKVKGJDwK"

def send_welcome_email_task(user_id, token):
    from .models import User  # import here to avoid circular imports
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        print(f"User {user_id} does not exist")
        return

    subject = "Welcome! Verify Your Account"
    html_content = f"""
        <p>Hello {user.first_name},</p>
        <p>Welcome! Your verification token is: <strong>{token}</strong></p>
        <p>Thank you for joining!</p>
    """

    try:
        resend.Emails.send({
            "from": "Procured Payment <onboarding@resend.dev>",
            "to": user.email,
            "subject": subject,
            "html": html_content,
        })
        print(f"Verification email sent to {user.email}")
    except Exception as e:
        print(f"Email sending error for {user.email}: {e}")
