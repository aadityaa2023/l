from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.db import models
from .models import User, StudentProfile, TeacherProfile, Address


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    """Custom User Admin"""
    
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    
    # Unfold customizations
    list_filter_submit = True
    list_fullwidth = True
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone')}),
        (_('Permissions'), {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_active', 'is_staff'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')

    # Allow platform admin users (role='admin' and is_staff=True) to manage users
    def _is_platform_admin(self, user):
        return getattr(user, 'is_authenticated', False) and getattr(user, 'role', '') == 'admin' and getattr(user, 'is_staff', False)

    def has_module_permission(self, request):
        # Allow access to the users app in admin for superusers and staff members.
        # Staff users are permitted here so platform/admin staff can manage users via admin.
        if request.user.is_superuser or request.user.is_staff:
            return True
        return False

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.is_staff:
            return True
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.is_staff:
            return True
        return False

    def has_add_permission(self, request):
        if request.user.is_superuser or request.user.is_staff:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.is_staff:
            return True
        return False


@admin.register(StudentProfile)
class StudentProfileAdmin(ModelAdmin):
    """Student Profile Admin"""
    
    list_display = ('user', 'total_courses_enrolled', 'total_listening_hours', 'notification_enabled', 'created_at')
    list_filter = ('notification_enabled', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'total_courses_enrolled', 'total_listening_hours')
    
    # Unfold customizations
    list_filter_submit = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Profile Information'), {'fields': ('bio', 'profile_picture', 'date_of_birth')}),
        (_('Preferences'), {'fields': ('preferred_language', 'notification_enabled')}),
        (_('Statistics'), {'fields': ('total_courses_enrolled', 'total_listening_hours')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(TeacherProfile)
class TeacherProfileAdmin(ModelAdmin):
    """Teacher Profile Admin"""
    
    list_display = ('user', 'expertise', 'is_verified', 'total_courses', 'total_students', 'average_rating', 'created_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'expertise')
    readonly_fields = ('created_at', 'updated_at', 'total_courses', 'total_students', 'average_rating', 'verification_date')
    
    # Unfold customizations
    list_filter_submit = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Profile Information'), {'fields': ('bio', 'profile_picture', 'expertise')}),
        (_('Verification'), {'fields': ('is_verified', 'verification_date')}),
        (_('Social Links'), {'fields': ('website', 'linkedin', 'twitter')}),
        (_('Statistics'), {'fields': ('total_courses', 'total_students', 'average_rating')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )
    
    actions = ['verify_teachers', 'unverify_teachers']
    
    def verify_teachers(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_verified=True, verification_date=timezone.now())
        self.message_user(request, f"{queryset.count()} teachers verified successfully.")
    verify_teachers.short_description = "Verify selected teachers"
    
    def unverify_teachers(self, request, queryset):
        queryset.update(is_verified=False, verification_date=None)
        self.message_user(request, f"{queryset.count()} teachers unverified.")
    unverify_teachers.short_description = "Unverify selected teachers"


@admin.register(Address)
class AddressAdmin(ModelAdmin):
    """Address Admin"""
    
    list_display = ('user', 'address_type', 'city', 'state', 'country', 'is_default', 'created_at')
    list_filter = ('address_type', 'is_default', 'country', 'created_at')
    search_fields = ('user__email', 'city', 'state', 'postal_code')
    readonly_fields = ('created_at', 'updated_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Address Details'), {'fields': ('address_type', 'street_address', 'city', 'state', 'postal_code', 'country')}),
        (_('Settings'), {'fields': ('is_default',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )
