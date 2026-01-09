"""
Custom decorators for platformadmin access control
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login


def platformadmin_required(view_func):
    """
    Decorator to check if user is a platformadmin
    A platformadmin is a user with role 'admin' and is_staff=True
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "You must be logged in to access this page.")
            # Redirect to login page and preserve `next` so user returns to platformadmin
            return redirect_to_login(request.get_full_path(), login_url=reverse('account_login'))
        
        # Check if user has admin role (platformadmin)
        if not (request.user.role == 'admin' and request.user.is_staff):
            messages.error(request, "You don't have permission to access this page.")
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def superadmin_required(view_func):
    """
    Decorator to check if user is a superuser (Django admin)
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "You must be logged in to access this page.")
            return redirect('account_login')
        
        if not request.user.is_superuser:
            messages.error(request, "You don't have permission to access this page.")
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def log_admin_action(action, content_type, object_id, object_repr, old_values=None, new_values=None, reason=''):
    """
    Utility function to log admin actions
    
    Args:
        action: 'create', 'update', 'delete', 'approve', 'reject', etc.
        content_type: Model name (e.g., 'User', 'Course', 'Payment')
        object_id: ID of the object being modified
        object_repr: String representation of the object
        old_values: Dict of previous values
        new_values: Dict of new values
        reason: Reason for the action
    """
    from django.contrib.auth import get_user_model
    from apps.platformadmin.models import AdminLog
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                response = view_func(request, *args, **kwargs)
                
                # Log the action
                AdminLog.objects.create(
                    admin=request.user,
                    action=action,
                    content_type=content_type,
                    object_id=str(object_id),
                    object_repr=object_repr,
                    old_values=old_values or {},
                    new_values=new_values or {},
                    reason=reason,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                
                return response
            except Exception as e:
                return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def get_client_ip(request):
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
