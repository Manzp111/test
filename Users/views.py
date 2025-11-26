# users/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_spectacular.utils import extend_schema, OpenApiExample
from django.db import transaction
from .user_serializer import UserRegistrationSerializer,UserSerializer
from .utils import api_response
from .models import VerificationToken,User
from .task import send_welcome_email_task
from .mixins import UserStatusMixin
from rest_framework_simplejwt.tokens import RefreshToken,TokenError
from django.core.mail import send_mail


class UserListAPIView(APIView):
    permission_classes = [permissions.AllowAny]  # Only logged-in users can see

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)




@extend_schema(
    tags=['Authentication'],
    summary="Register a new user account",
    description="""
### User Registration API  
This endpoint allows a new user to create an account.

**Features:**
- Validates unique email and phone
- Enforces strong password rules
- Returns a consistent response format with metadata
- Public — no authentication required
""",
    request=UserRegistrationSerializer,

    examples=[
        OpenApiExample(
            "User Registration Example",
            description="Example request body to create a new user",
            value={
                "email": "gilbert@gmail.com",
                "phone": "0781234567",
                "first_name": "Gilbert",
                "last_name": "Manzi",
                "password": "StrongPass@123",
                "password2": "StrongPass@123",
                "profile_picture": None
            }
        )
    ],
    methods=["POST"]
)
class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data, context={"request": request})

        # serializer = UserRegistrationSerializer(data=request.data)

        # Validate manually, no automatic exception
        serializer.is_valid(raise_exception=False)

        if serializer.errors:
            # Return the first error only
            first_field = next(iter(serializer.errors))
            first_msg = serializer.errors[first_field]
            return api_response(
                success=False,
                message=first_msg[0] if isinstance(first_msg, list) else str(first_msg),
                data=None,
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                user = serializer.create(serializer.validated_data)
                user.save()
                token_obj = VerificationToken.objects.create(user=user)
                print("")
                print(f"Verification token for {user.email}: {token_obj.token}")
                print("")
                # send_mail(
                #     subject="Welcome!",
                #     message=f"Your verification token is {token_obj.token}",
                #     from_email="noreply@example.com",
                #     recipient_list=[user.email],
                #     fail_silently=False,
                # )
                send_welcome_email_task.delay(user.id, str(token_obj.token))
        except Exception as e:
            # Catch any save error
            return api_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
                
            )
        user_serializer = UserRegistrationSerializer(user, context={"request": request})
        return api_response(
            success=True,
            message="User registered successfully",  
            data=user_serializer.data,             
            status_code=status.HTTP_201_CREATED
        )





@extend_schema(
    tags=['Authentication'],
    summary="Login a user and get JWT tokens",
    description="""
### User Login API
This endpoint allows an existing user to log in using their email and password.

**Behavior:**
- Checks if the user exists.
- Validates password correctness.
- Ensures the user is active and verified.
- Returns `access` and `refresh` JWT tokens on successful login.
- Returns meaningful error messages if login fails.

**Responses:**
- 200: Success with JWT tokens.
- 400: Missing email or password.
- 401: Incorrect password.
- 403: User inactive or not verified.
- 404: Email does not exist.
""",
    request=OpenApiExample(
        name="Login Request Example",
        value={
            "email": "user@example.com",
            "password": "StrongPass@123"
        },
        request_only=True
    ),

      examples=[
        OpenApiExample(
            "User login Example",
            description="Example request body to login to user",
            value={                              
                    "email": "gilbertnshimyimana11@gmail.com",
                    "password": "StrongPass@123"                  

            }
        )
    ],
   
    methods=["POST"]
)
class LoginAPIView(APIView, UserStatusMixin):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return api_response(
                success=False,
                message="Email and password are required",
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return api_response(
                success=False,
                message="Email does not exist",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )

        if not user.check_password(password):
            return api_response(
                success=False,
                message="Incorrect password",
                data=None,
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Check active and verified using mixin
        status_check = self.check_user_status(user)
        if status_check:
            return status_check

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        data = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "role": user.role
        }

        return api_response(
            success=True,
            message="Login successful",
            data=data,
            status_code=status.HTTP_200_OK
        )
    



class RefreshTokenAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Refresh JWT access token",
        description="Takes a refresh token and returns a new access token.",
        request={
            "type": dict,
            "properties": {
                "refresh": {"type": "string", "description": "Valid refresh token"}
            },
            "required": ["refresh"]
        },
  
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return api_response(
                success=False,
                message="Refresh token is required",
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)

            return api_response(
                success=True,
                message="Access token refreshed successfully",
                data={"access": new_access_token},
                status_code=status.HTTP_200_OK
            )

        except TokenError:
            return api_response(
                success=False,
                message="Invalid or expired refresh token",
                data=None,
                status_code=status.HTTP_401_UNAUTHORIZED
            )






@extend_schema(
    tags=['Authentication'],
    summary="Verify user account with token",
    description="""
### User Verification API
This endpoint allows a user to verify their account using a 6-digit verification token sent to their email.

**Behavior:**
- Checks if the token exists and is linked to the user.
- Checks if the token is expired.
- Marks the user as verified if valid.
- Returns meaningful error messages otherwise.

**Responses:**
- 200: Successful verification.
- 400: Missing token or email.
- 404: User or token not found.
- 410: Token expired.
""",
    request=OpenApiExample(
        name="Verification Request Example",
        value={
            "email": "user@example.com",
            "token": "123456"
        },
        request_only=True
    ),

    examples=[
        OpenApiExample(
            "User login Example",
            description="Example request body to login to user",
            value={                            
                   
                    "email": "gilbertnshimyimana11@gmail.com",
                    "token": "123456"


            }
        )
    ],
    methods=["POST"]
)
class VerifyAccountAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        token_value = request.data.get("token")

        if not email:
            return api_response(
                success=False,
                message="Email   are required",
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        if not token_value:
            return api_response(
                success=False,
                message="token are required",
                data=None,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return api_response(
                success=False,
                message="Email does not exist",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )

        try:
            token = VerificationToken.objects.get(user=user, token=token_value)
        except VerificationToken.DoesNotExist:
            return api_response(
                success=False,
                message="Invalid verification Token",
                data=None,
                status_code=status.HTTP_404_NOT_FOUND
            )

        if token.is_expired():
            return api_response(
                success=False,
                message="Verification token has expired",
                data=None,
                status_code=status.HTTP_410_GONE
            )

        # Mark user as verified
        user.is_verified = True
        user.save()

        # Delete token after successful verification
        token.delete()

        return api_response(
            success=True,
            message="Account verified successfully",
            data=None,
            status_code=status.HTTP_200_OK
        )
