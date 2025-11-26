from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, VerificationToken

# -------------------------
# Custom User Admin
# -------------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Define fieldsets to control which fields appear in the admin form
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone', 'profile_picture')}),
        ('Permissions', {'fields': ('role', 'is_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'registration_date')}),
    )
    
    # Fields to display in the list view
    list_display = ('first_name', 'last_name', 'phone', 'email', 'role', 'is_verified', 'is_active', 'is_staff')
    list_filter = ('role', 'is_verified', 'is_active', 'is_staff', 'registration_date')
    search_fields = ('email', 'phone', 'first_name', 'last_name')
    ordering = ('phone',)
    
    # Make sure these fields are editable
    readonly_fields = ('registration_date', 'last_login')
    
    # Specify which fields appear in the create user form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone', 'first_name', 'last_name', 'password1', 'password2', 'role'),
        }),
    )


# -------------------------
# VerificationToken Admin
# -------------------------
@admin.register(VerificationToken)
class VerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'expires_at', 'is_expired')
    readonly_fields = ('token', 'created_at', 'expires_at')
    search_fields = ('user__phone', 'user__email', 'token')
    list_filter = ('created_at',)

    # Custom method to show if token is expired
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired?'