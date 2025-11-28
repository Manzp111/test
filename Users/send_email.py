import resend
import os

resend.api_key = os.environ.get("RESEND_API_KEY")

def send_verification_email(to_email, code):
    return resend.Emails.send({
        "from": "Gilbe App <onboarding@resend.dev>",
        "to": to_email,
        "subject": "Your Verification Code",
        "html": f"<p>Your verification code is <strong>{code}</strong></p>",
    })
