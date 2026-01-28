"""
Role-Based Access Control (RBAC) for Platform Admin
Provides granular permissions for different admin roles
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
import logging

logger = logging.getLogger(__name__)


class AdminPermissions:
    """Define admin permission levels"""
    
    # Permission categories
    VIEW_DASHBOARD = 'view_dashboard'
    
    # User management permissions
    VIEW_USERS = 'view_users'
    MANAGE_USERS = 'manage_users'
    DELETE_USERS = 'delete_users'
    VERIFY_TEACHERS = 'verify_teachers'
    
    # Course management permissions
    VIEW_COURSES = 'view_courses'
    APPROVE_COURSES = 'approve_courses'
    REJECT_COURSES = 'reject_courses'
    DELETE_COURSES = 'delete_courses'
    FEATURE_COURSES = 'feature_courses'
    
    # Payment management permissions
    VIEW_PAYMENTS = 'view_payments'
    PROCESS_REFUNDS = 'process_refunds'
    VIEW_FINANCIAL_REPORTS = 'view_financial_reports'
    
    # Platform settings permissions
    VIEW_SETTINGS = 'view_settings'
    MODIFY_SETTINGS = 'modify_settings'
    
    # Analytics permissions
    VIEW_ANALYTICS = 'view_analytics'
    EXPORT_DATA = 'export_data'
    
    # Audit permissions
    VIEW_LOGS = 'view_logs'
    
    # Super admin permissions
    FULL_ACCESS = 'full_access'


class AdminRole:
    """Define admin roles and their permissions"""
    
    ROLES = {
        'super_admin': {
            'name': 'Super Admin',
            'description': 'Full platform access',
            'permissions': [AdminPermissions.FULL_ACCESS]
        },
        'content_moderator': {
            'name': 'Content Moderator',
            'description': 'Manages courses and approvals',
            'permissions': [
                AdminPermissions.VIEW_DASHBOARD,
                AdminPermissions.VIEW_COURSES,
                AdminPermissions.APPROVE_COURSES,
                AdminPermissions.REJECT_COURSES,
                AdminPermissions.FEATURE_COURSES,
                AdminPermissions.VIEW_USERS,
                AdminPermissions.VERIFY_TEACHERS,
                AdminPermissions.VIEW_LOGS,
            ]
        },
        'finance_admin': {
            'name': 'Finance Admin',
            'description': 'Manages payments and refunds',
            'permissions': [
                AdminPermissions.VIEW_DASHBOARD,
                AdminPermissions.VIEW_PAYMENTS,
                AdminPermissions.PROCESS_REFUNDS,
                AdminPermissions.VIEW_FINANCIAL_REPORTS,
                AdminPermissions.VIEW_ANALYTICS,
                AdminPermissions.EXPORT_DATA,
                AdminPermissions.VIEW_LOGS,
            ]
        },
        'user_support': {
            'name': 'User Support',
            'description': 'Manages users and support requests',
            'permissions': [
                AdminPermissions.VIEW_DASHBOARD,
                AdminPermissions.VIEW_USERS,
                AdminPermissions.MANAGE_USERS,
                AdminPermissions.VIEW_COURSES,
                AdminPermissions.VIEW_PAYMENTS,
                AdminPermissions.VIEW_LOGS,
            ]
        },
        'analytics_viewer': {
            'name': 'Analytics Viewer',
            'description': 'Read-only access to analytics',
            'permissions': [
                AdminPermissions.VIEW_DASHBOARD,
                AdminPermissions.VIEW_ANALYTICS,
                AdminPermissions.VIEW_USERS,
                AdminPermissions.VIEW_COURSES,
                AdminPermissions.VIEW_PAYMENTS,
                AdminPermissions.EXPORT_DATA,
            ]
        },
        'platform_admin': {
            'name': 'Platform Admin',
            'description': 'Standard admin access',
            'permissions': [
                AdminPermissions.VIEW_DASHBOARD,
                AdminPermissions.VIEW_USERS,
                AdminPermissions.MANAGE_USERS,
                AdminPermissions.VERIFY_TEACHERS,
                AdminPermissions.VIEW_COURSES,
                AdminPermissions.APPROVE_COURSES,
                AdminPermissions.REJECT_COURSES,
                AdminPermissions.FEATURE_COURSES,
                AdminPermissions.VIEW_PAYMENTS,
                AdminPermissions.PROCESS_REFUNDS,
                AdminPermissions.EXPORT_DATA,
                AdminPermissions.VIEW_ANALYTICS,
                AdminPermissions.VIEW_SETTINGS,
                AdminPermissions.VIEW_LOGS,
            ]
        }
    }


class PermissionChecker:
    """Check user permissions"""
    
    @staticmethod
    def get_user_role(user):
        """Get user's admin role from database"""
        if user.is_superuser:
            return 'super_admin'
        
        # Check if user has AdminRole assignment
        from apps.platformadmin.models import AdminRole as AdminRoleModel
        try:
            admin_role_obj = AdminRoleModel.objects.get(user=user)
            role = admin_role_obj.role
        except AdminRoleModel.DoesNotExist:
            # Default platform admins get 'platform_admin' role
            if user.role == 'admin' and user.is_staff:
                role = 'platform_admin'
            else:
                role = None
        
        return role
    
    @staticmethod
    def get_user_permissions(user):
        """Get all permissions for a user"""
        role = PermissionChecker.get_user_role(user)
        
        if not role:
            return []
        
        # Super admin has all permissions
        if role == 'super_admin':
            return [AdminPermissions.FULL_ACCESS]
        
        role_data = AdminRole.ROLES.get(role, {})
        return role_data.get('permissions', [])
    
    @staticmethod
    def has_permission(user, permission):
        """Check if user has a specific permission"""
        permissions = PermissionChecker.get_user_permissions(user)
        
        # Full access grants everything
        if AdminPermissions.FULL_ACCESS in permissions:
            return True
        
        return permission in permissions
    
    @staticmethod
    def has_any_permission(user, permission_list):
        """Check if user has any of the permissions in the list"""
        return any(PermissionChecker.has_permission(user, perm) for perm in permission_list)
    
    @staticmethod
    def has_all_permissions(user, permission_list):
        """Check if user has all permissions in the list"""
        return all(PermissionChecker.has_permission(user, perm) for perm in permission_list)


def permission_required(permission):
    """
    Decorator to check if user has a specific permission
    
    Usage:
        @permission_required(AdminPermissions.PROCESS_REFUNDS)
        def refund_payment(request, payment_id):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "You must be logged in to access this page.")
                return redirect('account_login')
            
            if not (request.user.role == 'admin' and request.user.is_staff):
                messages.error(request, "You don't have permission to access this page.")
                return redirect('home')
            
            # Check permission
            if not PermissionChecker.has_permission(request.user, permission):
                logger.warning(f"User {request.user.email} denied access to {view_func.__name__} - missing permission: {permission}")
                # For export endpoints or requests expecting a file/json, return 403 instead of redirecting
                path = request.path or ''
                accept = request.META.get('HTTP_ACCEPT', '')
                is_export_endpoint = '/export/' in path or 'export' in view_func.__name__.lower()
                expects_csv = 'text/csv' in accept or path.endswith('.csv')
                is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

                if is_export_endpoint or expects_csv or is_ajax:
                    # Provide a JSON response for AJAX or a plain 403 for CSV/file endpoints
                    if is_ajax:
                        return JsonResponse({'detail': "You don't have permission to perform this action."}, status=403)
                    return HttpResponseForbidden("You don't have permission to perform this action.")

                messages.error(request, "You don't have permission to perform this action.")
                return redirect('platformadmin:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def any_permission_required(*permissions):
    """
    Decorator to check if user has any of the specified permissions
    
    Usage:
        @any_permission_required(AdminPermissions.VIEW_USERS, AdminPermissions.MANAGE_USERS)
        def user_list(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "You must be logged in to access this page.")
                return redirect('account_login')
            
            if not (request.user.role == 'admin' and request.user.is_staff):
                messages.error(request, "You don't have permission to access this page.")
                return redirect('home')
            
            # Check if user has any of the permissions
            if not PermissionChecker.has_any_permission(request.user, permissions):
                logger.warning(f"User {request.user.email} denied access to {view_func.__name__} - missing any of: {permissions}")
                path = request.path or ''
                accept = request.META.get('HTTP_ACCEPT', '')
                is_export_endpoint = '/export/' in path or 'export' in view_func.__name__.lower()
                expects_csv = 'text/csv' in accept or path.endswith('.csv')
                is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

                if is_export_endpoint or expects_csv or is_ajax:
                    if is_ajax:
                        return JsonResponse({'detail': "You don't have permission to perform this action."}, status=403)
                    return HttpResponseForbidden("You don't have permission to perform this action.")

                messages.error(request, "You don't have permission to perform this action.")
                return redirect('platformadmin:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def all_permissions_required(*permissions):
    """
    Decorator to check if user has all of the specified permissions
    
    Usage:
        @all_permissions_required(AdminPermissions.VIEW_PAYMENTS, AdminPermissions.PROCESS_REFUNDS)
        def process_refund(request, payment_id):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "You must be logged in to access this page.")
                return redirect('account_login')
            
            if not (request.user.role == 'admin' and request.user.is_staff):
                messages.error(request, "You don't have permission to access this page.")
                return redirect('home')
            
            # Check if user has all permissions
            if not PermissionChecker.has_all_permissions(request.user, permissions):
                logger.warning(f"User {request.user.email} denied access to {view_func.__name__} - missing all of: {permissions}")
                path = request.path or ''
                accept = request.META.get('HTTP_ACCEPT', '')
                is_export_endpoint = '/export/' in path or 'export' in view_func.__name__.lower()
                expects_csv = 'text/csv' in accept or path.endswith('.csv')
                is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

                if is_export_endpoint or expects_csv or is_ajax:
                    if is_ajax:
                        return JsonResponse({'detail': "You don't have permission to perform this action."}, status=403)
                    return HttpResponseForbidden("You don't have permission to perform this action.")

                messages.error(request, "You don't have permission to perform this action.")
                return redirect('platformadmin:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Context processor to add permissions to templates
def permission_context(request):
    """Add user permissions to template context"""
    if request.user.is_authenticated and request.user.role == 'admin':
        permissions = PermissionChecker.get_user_permissions(request.user)
        role = PermissionChecker.get_user_role(request.user)
        role_data = AdminRole.ROLES.get(role, {})
        
        return {
            'admin_permissions': permissions,
            'admin_role': role,
            'admin_role_name': role_data.get('name', 'Unknown'),
            'has_full_access': AdminPermissions.FULL_ACCESS in permissions,
        }
    
    return {}
