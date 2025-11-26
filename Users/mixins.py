from rest_framework import status
from .utils import api_response

class UserStatusMixin:
    """
    Mixin to check if a user is active and verified.
    """

    def check_user_status(self, user):
        if not user.is_active:
            return api_response(
                success=False,
                message="User account is inactive",
                data=None,
                status_code=status.HTTP_403_FORBIDDEN
            )

        if not user.is_verified:
            return api_response(
                success=False,
                message="User account is not verified",
                data=None,
                status_code=status.HTTP_403_FORBIDDEN
            )

        return None
