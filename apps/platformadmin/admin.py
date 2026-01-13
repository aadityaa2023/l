"""
Django Admin Configuration for PlatformAdmin
This is for the Django default admin panel (superuser only)
Limited to basic user management
"""
from django.contrib import admin
from django.contrib.auth import get_user_model
from apps.platformadmin.models import (
    AdminLog, CourseApproval, DashboardStat, PlatformSetting,
    LoginHistory, CMSPage, FAQ, Announcement, InstructorPayout,
    VideoSettings, CourseAssignment
)

User = get_user_model()


@admin.register(CourseAssignment)
class CourseAssignmentAdmin(admin.ModelAdmin):
    """Admin interface for course assignments"""
    list_display = ['course', 'teacher', 'status', 'assigned_by', 'assigned_at', 'can_edit_content']
    list_filter = ['status', 'can_edit_content', 'can_edit_details', 'can_publish', 'assigned_at']
    search_fields = ['course__title', 'teacher__email', 'assigned_by__email']
    readonly_fields = ['id', 'assigned_at', 'accepted_at', 'rejected_at', 'revoked_at', 'updated_at']
    date_hierarchy = 'assigned_at'
    
    fieldsets = (
        ('Assignment Info', {
            'fields': ('course', 'teacher', 'assigned_by', 'status')
        }),
        ('Permissions', {
            'fields': ('can_edit_content', 'can_edit_details', 'can_publish')
        }),
        ('Notes', {
            'fields': ('assignment_notes', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('assigned_at', 'accepted_at', 'rejected_at', 'revoked_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    """Admin interface for activity logs"""
    list_display = ['admin', 'action', 'content_type', 'object_repr', 'created_at']
    list_filter = ['action', 'content_type', 'created_at']
    search_fields = ['admin__email', 'object_repr', 'reason']
    readonly_fields = ['id', 'admin', 'action', 'content_type', 'object_id', 'object_repr', 
                       'old_values', 'new_values', 'reason', 'ip_address', 'user_agent', 'created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CourseApproval)
class CourseApprovalAdmin(admin.ModelAdmin):
    """Admin interface for course approvals"""
    list_display = ['course', 'status', 'reviewed_by', 'reviewed_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['course__title', 'reviewed_by__email']
    readonly_fields = ['id', 'course', 'submitted_at', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(DashboardStat)
class DashboardStatAdmin(admin.ModelAdmin):
    """Admin interface for dashboard statistics"""
    list_display = ['date', 'total_users', 'total_courses', 'total_revenue', 'created_at']
    list_filter = ['date']
    search_fields = ['date']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'date'


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    """Admin interface for platform settings"""
    list_display = ['key', 'setting_type', 'is_public', 'updated_at']
    list_filter = ['setting_type', 'is_public']
    search_fields = ['key', 'description']


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    """Admin interface for login history"""
    list_display = ['email', 'status', 'ip_address', 'browser', 'attempted_at']
    list_filter = ['status', 'attempted_at']
    search_fields = ['email', 'ip_address', 'user__email']
    readonly_fields = ['user', 'email', 'status', 'ip_address', 'user_agent', 'device_type',
                       'browser', 'os', 'country', 'city', 'session_key', 'attempted_at', 'logout_at']
    date_hierarchy = 'attempted_at'
    
    def has_add_permission(self, request):
        return False


@admin.register(CMSPage)
class CMSPageAdmin(admin.ModelAdmin):
    """Admin interface for CMS pages"""
    list_display = ['title', 'slug', 'status', 'is_in_menu', 'created_at']
    list_filter = ['status', 'is_in_menu']
    search_fields = ['title', 'slug', 'content']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """Admin interface for FAQs"""
    list_display = ['question', 'category', 'order', 'is_active', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['question', 'answer']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """Admin interface for announcements"""
    list_display = ['title', 'announcement_type', 'display_location', 'is_active', 'start_date', 'end_date']
    list_filter = ['announcement_type', 'display_location', 'is_active']
    search_fields = ['title', 'message']
    date_hierarchy = 'created_at'


@admin.register(InstructorPayout)
class InstructorPayoutAdmin(admin.ModelAdmin):
    """Admin interface for instructor payouts"""
    list_display = ['instructor', 'net_amount', 'status', 'period_start', 'period_end', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['instructor__email', 'transaction_reference']
    readonly_fields = ['gross_amount', 'platform_commission', 'net_amount', 'commission_rate',
                       'period_start', 'period_end', 'requested_at', 'processed_at']
    date_hierarchy = 'created_at'



@admin.register(VideoSettings)
class VideoSettingsAdmin(admin.ModelAdmin):
    """Admin interface for video settings"""
    list_display = ['enable_drm', 'enable_watermark', 'allow_download_default', 
                    'max_video_quality', 'max_concurrent_devices', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not VideoSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False

class PlatformSettingAdmin(admin.ModelAdmin):
    """Admin interface for platform settings"""
    list_display = ['key', 'value', 'setting_type', 'is_public', 'updated_at']
    list_filter = ['setting_type', 'is_public']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']


# Customize the User admin to be simple (for superuser only)
# Unregister the existing User admin if it exists
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class SimpleUserAdmin(admin.ModelAdmin):
    """Simplified User admin for superuser - basic user management only"""
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('email', 'first_name', 'last_name', 'phone')
        }),
        ('Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'last_login')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Show all users for superusers
        return qs


# Customize admin site header and title
admin.site.site_header = "LeQ Superadmin Panel"
admin.site.site_title = "LeQ Admin"
admin.site.index_title = "User Management"

