from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from Users.models import User, VerificationToken, normalize_phone


class TestNormalizePhone(TestCase):

    def test_valid_local_phone(self):
        self.assertEqual(normalize_phone("0788888888"), "+250788888888")

    def test_valid_international_phone(self):
        self.assertEqual(normalize_phone("+250788888888"), "+250788888888")

    def test_invalid_characters(self):
        with self.assertRaises(ValidationError):
            normalize_phone("07ab888888")

    def test_invalid_format(self):
        with self.assertRaises(ValidationError):
            normalize_phone("123456")


class TestUserModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            phone="0788888888",
            email="manzi@gmail.com",
            first_name="John",
            last_name="Doe",
            password="password123"
        )

    def test_user_is_created(self):
        self.assertEqual(self.user.phone, "+250788888888")
        self.assertEqual(self.user.email, "manzi@gmail.com")
        self.assertTrue(self.user.check_password("password123"))
        self.assertFalse(self.user.is_staff)
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.is_superuser)

    def test_superuser_creation(self):
        admin = User.objects.create_superuser(
            phone="0799999999",
            email="manzi11@gmail.com", 
            first_name="Admin",
            last_name="User",
            password="adminpass"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_verified)

    def test_unique_phone_constraint(self):
        with self.assertRaises(Exception):
            User.objects.create_user(
                phone="0788888888",
                email="manzi12@gmail.com",
                first_name="A",
                last_name="B",
                password="pass"
            )

    def test_phone_is_normalized_on_save(self):
        user = User(
            phone="0781234567",
            email="manzi13@gmail.com",
            first_name="X",
            last_name="Y"
        )
        user.set_password("pass")
        user.save()
        self.assertEqual(user.phone, "+250781234567")


class TestVerificationToken(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            phone="0788888899",
            email="manzi14@gmail.com",
            first_name="Token",
            last_name="Manzi",
            password="mypassword"
        )

        self.token = VerificationToken.objects.create(
            user=self.user
        )

    def test_token_is_created(self):
        self.assertIsNotNone(self.token.token)
        self.assertIsNotNone(self.token.created_at)
        self.assertIsNotNone(self.token.expires_at)

    def test_token_default_expiration_is_10_minutes(self):
        expected_expiry = self.token.created_at + timedelta(minutes=10)
        self.assertAlmostEqual(self.token.expires_at, expected_expiry, delta=timedelta(seconds=1))

    def test_token_not_expired(self):
        self.assertFalse(self.token.is_expired())

    def test_token_is_expired(self):
        self.token.expires_at = timezone.now() - timedelta(minutes=1)
        self.assertTrue(self.token.is_expired())
