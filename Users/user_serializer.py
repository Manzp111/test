# users/serializers.py

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, normalize_phone


class UserRegistrationSerializer(serializers.ModelSerializer):

    email = serializers.EmailField(
        required=True,
        error_messages={"required": "Email is required."}
    )
    phone = serializers.CharField(
        required=True,
        error_messages={"required": "Phone number is required."}
    )
    first_name = serializers.CharField(
        required=True,
        error_messages={"required": "First name is required."}
    )
    last_name = serializers.CharField(
        required=True,
        error_messages={"required": "Last name is required."}
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        help_text="Password must be strong",
        error_messages={"required": "Password is required."}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        help_text="Enter the same password for confirmation",
        error_messages={"required": "Password confirmation is required."}
    )
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "email", "phone", "first_name", "last_name",
            "password", "password2", "profile_picture_url",
            "is_verified", "is_active", "is_staff"
        )
        extra_kwargs = {
            "email": {"validators": []},
            "phone": {"validators": []},
            "id": {"read_only": True},
            "is_verified": {"read_only": True},
            "is_active": {"read_only": True},
            "is_staff": {"read_only": True},
        }

    def get_profile_picture_url(self, obj):
        request = self.context.get('request')
        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            try:
                return request.build_absolute_uri(obj.profile_picture.url)
            except ValueError:
                return None
        return None

    def validate(self, attrs):
        errors = {}

        # Required fields check
        required_fields = ["email", "phone", "first_name", "last_name", "password", "password2"]
        for field in required_fields:
            if not attrs.get(field):
                errors[field] = [f"{field.replace('_', ' ').capitalize()} is required"]

        # Stop further validation if required fields are missing
        if errors:
            raise serializers.ValidationError(errors)

        # Phone normalization
        try:
            attrs["phone"] = normalize_phone(attrs["phone"])
        except ValidationError as e:
            errors["phone"] = [str(e)]

        # Password match
        if attrs["password"] != attrs["password2"]:
            errors["password2"] = ["Passwords do not match"]

        # Email uniqueness
        if User.objects.filter(email=attrs["email"]).exists():
            errors["email"] = ["Email already exists"]

        # Phone uniqueness
        if User.objects.filter(phone=attrs["phone"]).exists():
            errors["phone"] = ["Phone number already exists"]

        # Password strength (Django validator)
        try:
            validate_password(attrs["password"])
        except ValidationError as e:
            errors["password"] = e.messages

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        return user




class UserSerializer(serializers.ModelSerializer):
    """
    Basic user serializer for displaying user info in related objects
    """
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['email', 'phone', 'first_name', 'last_name', 'full_name', 'role']
        read_only_fields = ['email', 'phone', 'first_name', 'last_name', 'full_name', 'role']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
