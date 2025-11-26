# users/models.py

import uuid
import re
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import random
# from fernet_fields import EncryptedCharField, EncryptedTextField
from encrypted_model_fields.fields import EncryptedCharField,EncryptedEmailField


USER_ROLES = (
   ("staff", "Staff"),
    ("manager", "Approval Level 1"),            
    ("general_manager", "Approval Level 2"),
    ("finance", "Finance"),
    ("admin", "Admin"),
)


# PHONE NORMALIZATION FUNCTION

def normalize_phone(phone):
    phone = phone.replace(" ", "").replace("-", "")

    if not re.match(r"^\+?\d+$", phone):
        raise ValidationError("Phone number contains invalid characters")
    
    # Already correct  format
    if phone.startswith("+2507") and len(phone) == 13:
        return phone

    
    if phone.startswith("07") and len(phone) == 10:
        return "+250" + phone[1:]

    raise ValidationError("Phone number must be 07xxxxxxxx or +2507xxxxxxxx")




# CUSTOM USER MANAGER

class UserManager(BaseUserManager):

    def create_user(self, phone, email, first_name, last_name, password=None, **extra_fields):
        if not phone:
            raise ValidationError("Phone number is required")
        if not email:
            raise ValidationError("Email is required")

        phone = normalize_phone(phone)
        email = self.normalize_email(email)

        user = self.model(
            phone=phone,
            email=email,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)
        return user


    def create_superuser(self, phone, email, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)

        return self.create_user(phone, email, first_name, last_name, password, **extra_fields)



# USER MODEL
class User(AbstractBaseUser, PermissionsMixin):

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)

    phone = EncryptedCharField(
        max_length=13,
        unique=True,
        validators=[
            RegexValidator(
                r"^(07\d{8}|\+2507\d{8})$",
                message="Phone number must be 07xxxxxxxx or +2507xxxxxxxx and 10 max long",
            )
        ],
    )

    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(upload_to="profile_pics/", blank=True, null=True)

    role = models.CharField(max_length=20, choices=USER_ROLES, default="staff")
    registration_date = models.DateTimeField(default=timezone.now)

    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone", "first_name", "last_name"]

    objects = UserManager()

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone})"








# VERIFICATION TOKEN MODEL
def generate_6_digit_token():
    return random.randint(100000, 999999) 


class VerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_tokens")
    
    token = models.CharField(max_length=6, default=generate_6_digit_token, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Token for {self.user.phone}"
