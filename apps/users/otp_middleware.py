"""
OTP Middleware for protecting views.

This middleware can be used to enforce OTP verification for login if enabled.
By default, OTP is only required during signup for email verification.
Login does not require OTP verification.
"""

import re
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings

from .otp_utils import is_otp_verified_session


class OTPVerificationMiddleware:
    """
    Middleware to optionally require OTP verification for authenticated users.
    
    By default, this middleware is disabled (OTP only for signup).
    If enabled via settings, users who login must verify OTP before accessing protected views.
    
    Configuration in settings.py:
        OTP_REQUIRED_FOR_LOGIN = False  # Default: OTP only for signup, not login
        OTP_EXEMPT_URLS = ['/admin/', '/api/']  # URLs exempt from OTP check
    """
    
    # URLs that don't require OTP verification
    DEFAULT_EXEMPT_PATTERNS = [
        r'^/admin/',
        r'^/api/',
        r'^/accounts/logout/',
        r'^/users/logout/',
        r'^/users/otp/',
        r'^/static/',
        r'^/media/',
        r'^/__reload__/',  # Django browser reload
        r'^/favicon\.ico$',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Get exempt patterns from settings or use defaults
        custom_exempt = getattr(settings, 'OTP_EXEMPT_URLS', [])
        self.exempt_patterns = [
            re.compile(pattern) 
            for pattern in self.DEFAULT_EXEMPT_PATTERNS + list(custom_exempt)
        ]
        
        # Check if OTP is required for login (default: False - OTP only for signup)
        self.otp_required = getattr(settings, 'OTP_REQUIRED_FOR_LOGIN', False)
    
    def __call__(self, request):
        # Skip if OTP verification is disabled
        if not self.otp_required:
            return self.get_response(request)
        
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Skip for exempt URLs
        path = request.path
        if self._is_exempt(path):
            return self.get_response(request)
        
        # Check if user has verified OTP for this session
        if not is_otp_verified_session(request, 'login'):
            # Check if this is a fresh login that needs OTP
            # Only redirect if the session indicates OTP is pending
            otp_pending = request.session.get('otp_pending_user_pk')
            
            if otp_pending:
                messages.warning(request, 'Please verify OTP to continue.')
                return redirect('users:otp_verify')
        
        return self.get_response(request)
    
    def _is_exempt(self, path: str) -> bool:
        """Check if the path is exempt from OTP verification."""
        return any(pattern.match(path) for pattern in self.exempt_patterns)


class OTPRequiredMixin:
    """
    Mixin for class-based views that require OTP verification.
    
    Note: This is only applicable if OTP_REQUIRED_FOR_LOGIN is enabled in settings.
    By default, OTP is only required for signup, not login.
    
    Usage:
        class MyProtectedView(OTPRequiredMixin, View):
            def get(self, request):
                ...
    """
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not is_otp_verified_session(request, 'login'):
                messages.warning(request, 'Please verify OTP to access this page.')
                return redirect('users:otp_verify')
        return super().dispatch(request, *args, **kwargs)
