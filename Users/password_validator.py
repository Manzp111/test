import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class StrongPasswordValidator:
    """
    Validates that the password has:
      - At least 1 uppercase
      - At least 1 lowercase
      - At least 1 digit
      - At least 1 special character
      - Not similar to email, phone, first_name, last_name
      - Minimum length 8
    """

    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError(_("Password must be at least 8 characters long"))

        if not re.search(r"[A-Z]", password):
            raise ValidationError(_("Password must contain at least 1 uppercase letter"))

        if not re.search(r"[a-z]", password):
            raise ValidationError(_("Password must contain at least 1 lowercase letter"))

        if not re.search(r"\d", password):
            raise ValidationError(_("Password must contain at least 1 digit"))

        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
            raise ValidationError(_("Password must contain at least 1 special character"))

        # Ensure password does not contain user's personal info
        if user:
            user_fields = [user.email, getattr(user, "phone", ""), user.first_name, user.last_name]
            for field in user_fields:
                if field and field.lower() in password.lower():
                    raise ValidationError(_("Password cannot contain your personal information"))

    def get_help_text(self):
        return _(
            "Your password must contain at least 1 uppercase letter, 1 lowercase letter, "
            "1 digit, 1 special character, be at least 8 characters long, "
            "and not include your email, phone, or name."
        )
