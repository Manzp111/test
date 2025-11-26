from django.urls import path
from .views import RegisterAPIView,LoginAPIView,VerifyAccountAPIView,UserListAPIView,RefreshTokenAPIView

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path('login/', LoginAPIView.as_view(), name='login'),
    path("auth/refresh/", RefreshTokenAPIView.as_view(), name="token_refresh"),
    path('verify/', VerifyAccountAPIView.as_view(), name='verify_account'),
    path("list/", UserListAPIView.as_view(), name="user-list"),

]
