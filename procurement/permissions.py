# requests/permissions.py
from rest_framework import permissions

class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'staff'

class IsApprover(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated 
            and request.user.role in ['manager', 'general_manager']
        )

class IsFinance(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'finance'