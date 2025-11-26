from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from Users.models import User, VerificationToken
from unittest.mock import patch


class RegisterAPIViewTest(APITestCase):

    def setUp(self):
        self.url = reverse("register")
        self.user_data = {
            "email": "testuser@example.com",
            "phone": "0781234567",
            "first_name": "Test",
            "last_name": "User",
            "password": "StrongPass@123",
            "password2": "StrongPass@123",
            "profile_picture": None
        }

    @patch("Users.views.send_welcome_email_task.delay")
    def test_successful_registration(self, mock_send_email):
        response = self.client.post(self.url, self.user_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "User registered successfully")
        self.assertIsNone(response.data["errors"])

        # Check DB
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertEqual(user.email, self.user_data["email"])

        # Check verification token
        self.assertTrue(VerificationToken.objects.filter(user=user).exists())
        token = VerificationToken.objects.get(user=user)
        mock_send_email.assert_called_once_with(user.id, str(token.token))

    def test_missing_required_fields(self):
        data = {}
        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Email is required.")  # check the first field's error message

        expected_errors = ["email", "phone", "first_name", "last_name", "password", "password2"]
        custom_messages = {
            "email": "Email is required.",
            "phone": "Phone number is required.",
            "first_name": "First name is required.",
            "last_name": "Last name is required.",
            "password": "Password is required.",
            "password2": "Password confirmation is required.",
        }

        # for field in expected_errors:
        #     self.assertIn(field, response.data["errors"])
        #     self.assertIn(custom_messages[field], response.data["errors"][field])


    def test_password_mismatch(self):
        data = self.user_data.copy()
        data["password2"] = "WrongPass@123"

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Passwords do not match")

    def test_duplicate_email(self):
        User.objects.create_user(
            email=self.user_data["email"],
            phone="0799999999",
            first_name="Existing",
            last_name="User",
            password="StrongPass@123"
        )

        response = self.client.post(self.url, self.user_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Email already exists")

    def test_duplicate_phone(self):
        User.objects.create_user(
            email="new@example.com",
            phone=self.user_data["phone"],
            first_name="Existing",
            last_name="User",
            password="StrongPass@123"
        )

        response = self.client.post(self.url, self.user_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Phone number already exists")

    def test_weak_password(self):
        data = self.user_data.copy()
        data["password"] = data["password2"] = "123"

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Password must be at least 8 characters long")






class LoginAPIViewTest(APITestCase):

    def setUp(self):
        self.url = reverse("login")
        self.user_password = "StrongPass@123"
        self.user = User.objects.create_user(
            email="testuser@example.com",
            phone="0781234567",
            first_name="Test",
            last_name="User",
            password=self.user_password,
            is_verified=True,
            is_active=True
        )

    def test_successful_login(self):
        """Test login with correct credentials returns JWT tokens."""
        data = {"email": self.user.email, "password": self.user_password}
        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Login successful")
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])

    def test_missing_email_or_password(self):
        """Test login fails if email or password is missing."""
        data = {"email": self.user.email}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "Email and password are required")

    def test_email_does_not_exist(self):
        """Test login fails if email is not found."""
        data = {"email": "notfound@example.com", "password": "any"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "Email does not exist")

    def test_incorrect_password(self):
        """Test login fails if password is wrong."""
        data = {"email": self.user.email, "password": "WrongPass@123"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["message"], "Incorrect password")

    def test_inactive_user(self):
        """Test login fails if user is inactive."""
        self.user.is_active = False
        self.user.save()
        data = {"email": self.user.email, "password": self.user_password}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["message"], "User account is inactive")


    def test_unverified_user(self):
        """Test login fails if user is not verified."""
        self.user.is_verified = False
        self.user.save()
        data = {"email": self.user.email, "password": self.user_password}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["message"], "User account is not verified")

