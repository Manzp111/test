import resend

# Direct API key
resend.api_key = "re_D1fTNEDG_8MyXm73aga5gUZPEKVKGJDwK"

def send_verification_email(to_email, token):
    try:
        return resend.Emails.send({
            "from": "Procured payment <onboarding@resend.dev>",
            "to": to_email,
            "subject": "Your Verification Code",
            "html": f"<p>Your verification code is <strong>{token}</strong></p>",
        })
    except Exception as e:
        print("Email sending error:", e)
        return None


# import os
# from sendgrid import SendGridAPIClient
# from sendgrid.helpers.mail import Mail

# message = Mail(
#     from_email='from_email@example.com',
#     to_emails='to@example.com',
#     subject='Sending with Twilio SendGrid is Fun',
#     html_content='<strong>and easy to do anywhere, even with Python</strong>')
# try:
#     sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
#     # sg.set_sendgrid_data_residency("eu")
#     # uncomment the above line if you are sending mail using a regional EU subuser
#     response = sg.send(message)
#     print(response.status_code)
#     print(response.body)
#     print(response.headers)
# except Exception as e:
#     print(e.message)


from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings

def send_verification_email_glid(to_email, token):
    message = Mail(
        from_email=settings.FROM_EMAIL,
        to_emails=to_email,
        subject="Your Verification Code",
        html_content=f"<p>Your verification code is <strong>{token}</strong></p>"
    )

    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return True
    except Exception as e:
        print("SendGrid Error:", e)
        return False
