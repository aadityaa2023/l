"""
Rate limiting and security middleware for platformadmin
Protects against brute force and excessive requests
"""
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.conf import settings
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Simple in-memory storage for rate limiting
_rate_limit_storage = defaultdict(lambda: defaultdict(int))
_violation_storage = defaultdict(int)
_lockout_storage = defaultdict(lambda: None)


class RateLimitMiddleware:
    """
    Rate limiting middleware for platform admin endpoints
    Limits requests per IP address per time window
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Configuration
        self.rate_limit = getattr(settings, 'ADMIN_RATE_LIMIT', 100)  # requests per window
        self.time_window = getattr(settings, 'ADMIN_RATE_WINDOW', 60)  # seconds
        self.lockout_duration = getattr(settings, 'ADMIN_LOCKOUT_DURATION', 300)  # 5 minutes
        self.max_violations = getattr(settings, 'ADMIN_MAX_VIOLATIONS', 3)
    
    def __call__(self, request):
        # Only apply to platformadmin URLs
        if not request.path.startswith('/platformadmin/'):
            return self.get_response(request)
        
        # Skip for static files
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)
        
        # Get client IP
        ip_address = self.get_client_ip(request)
        
        # Check if IP is locked out
        if self.is_locked_out(ip_address):
            logger.warning(f"Locked out IP attempted access: {ip_address}")
            return HttpResponseForbidden("Too many requests. Please try again later.")
        
        # Check rate limit
        if not self.check_rate_limit(ip_address):
            # Record violation
            self.record_violation(ip_address)
            
            logger.warning(f"Rate limit exceeded for IP: {ip_address}")
            return JsonResponse({
                'error': 'Rate limit exceeded. Please slow down.'
            }, status=429)
        
        # Process request
        response = self.get_response(request)
        
        # Record successful request
        self.record_request(ip_address)
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def check_rate_limit(self, ip_address):
        """Check if IP is within rate limit"""
        now = timezone.now()
        current_window = int(now.timestamp()) // self.time_window
        request_count = _rate_limit_storage[ip_address].get(current_window, 0)
        
        return request_count < self.rate_limit
    
    def record_request(self, ip_address):
        """Record a request from IP address"""
        now = timezone.now()
        current_window = int(now.timestamp()) // self.time_window
        _rate_limit_storage[ip_address][current_window] += 1
        
        # Clean old entries
        cutoff_time = current_window - 1
        for window in list(_rate_limit_storage[ip_address].keys()):
            if window < cutoff_time:
                del _rate_limit_storage[ip_address][window]
    
    def record_violation(self, ip_address):
        """Record a rate limit violation"""
        _violation_storage[ip_address] += 1
        
        # Lock out if too many violations
        if _violation_storage[ip_address] >= self.max_violations:
            _lockout_storage[ip_address] = timezone.now() + timedelta(seconds=self.lockout_duration)
            logger.error(f"IP locked out due to excessive violations: {ip_address}")
    
    def is_locked_out(self, ip_address):
        """Check if IP is currently locked out"""
        lockout_time = _lockout_storage.get(ip_address)
        if lockout_time and timezone.now() < lockout_time:
            return True
        elif lockout_time and timezone.now() >= lockout_time:
            # Clean expired lockout
            del _lockout_storage[ip_address]
            _violation_storage[ip_address] = 0
        return False


class AdminActivityLoggerMiddleware:
    """
    Middleware to log all admin activity for security audit
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to platformadmin URLs
        if not request.path.startswith('/platformadmin/'):
            return self.get_response(request)
        
        # Skip for static files and GET requests to view pages
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or
            request.method == 'GET'):
            return self.get_response(request)
        
        # Log the request
        if request.user.is_authenticated and request.user.role == 'admin':
            logger.info(
                f"Admin action: {request.user.email} "
                f"{request.method} {request.path} "
                f"from {self.get_client_ip(request)}"
            )
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CSRFEnhancedMiddleware:
    """
    Enhanced CSRF protection for critical admin actions
    Requires additional confirmation for destructive operations
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Define critical paths that need extra protection
        self.critical_paths = [
            '/platformadmin/users/bulk-action/',
            '/platformadmin/payments/bulk-refund/',
            '/platformadmin/system/clear-cache/',
        ]
    
    def __call__(self, request):
        # Check if this is a critical action
        if request.path in self.critical_paths and request.method == 'POST':
            # Check for confirmation token
            confirmation = request.POST.get('confirm', '')
            
            if not confirmation:
                logger.warning(
                    f"Critical action without confirmation: "
                    f"{request.user.email if request.user.is_authenticated else 'Anonymous'} "
                    f"{request.path}"
                )
                return JsonResponse({
                    'error': 'This action requires explicit confirmation'
                }, status=400)
        
        response = self.get_response(request)
        return response


class IPWhitelistMiddleware:
    """
    Optional middleware to restrict admin access to whitelisted IPs
    Configure ADMIN_IP_WHITELIST in settings to enable
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.whitelist = getattr(settings, 'ADMIN_IP_WHITELIST', None)
        self.enabled = self.whitelist is not None
    
    def __call__(self, request):
        # Only apply if whitelist is configured
        if not self.enabled:
            return self.get_response(request)
        
        # Only apply to platformadmin URLs
        if not request.path.startswith('/platformadmin/'):
            return self.get_response(request)
        
        # Get client IP
        ip_address = self.get_client_ip(request)
        
        # Check whitelist
        if ip_address not in self.whitelist:
            logger.warning(f"Blocked admin access from non-whitelisted IP: {ip_address}")
            return HttpResponseForbidden(
                "Access denied. Your IP address is not authorized to access the admin panel."
            )
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SessionSecurityMiddleware:
    """
    Enhanced session security for admin users
    Implements session timeout and IP validation
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.session_timeout = getattr(settings, 'ADMIN_SESSION_TIMEOUT', 3600)  # 1 hour
    
    def __call__(self, request):
        # Only apply to authenticated admin users
        if (request.user.is_authenticated and 
            request.user.role == 'admin' and 
            request.path.startswith('/platformadmin/')):
            
            # Check session timeout
            last_activity = request.session.get('last_activity')
            if last_activity:
                from datetime import datetime
                last_activity_time = datetime.fromisoformat(last_activity)
                now = timezone.now()
                
                if (now - last_activity_time).total_seconds() > self.session_timeout:
                    logger.info(f"Admin session expired for {request.user.email}")
                    from django.contrib.auth import logout
                    logout(request)
                    from django.shortcuts import redirect
                    from django.contrib import messages
                    messages.warning(request, "Your session has expired. Please log in again.")
                    return redirect('account_login')
            
            # Update last activity
            request.session['last_activity'] = timezone.now().isoformat()
            
            # Validate IP hasn't changed (optional, can be strict)
            session_ip = request.session.get('admin_ip')
            current_ip = self.get_client_ip(request)
            
            if not session_ip:
                request.session['admin_ip'] = current_ip
            elif session_ip != current_ip:
                logger.warning(
                    f"IP address changed for admin session: "
                    f"{request.user.email} from {session_ip} to {current_ip}"
                )
                # Optionally log out user
                # For now, just log the warning
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
