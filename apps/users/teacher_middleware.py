"""
Teacher Redirect Middleware
Automatically redirects teachers to their dashboard instead of home page
"""
from django.shortcuts import redirect
from django.urls import reverse
import re


class TeacherRedirectMiddleware:
    """
    Middleware to automatically redirect teachers to their dashboard
    when they try to access the home page or student-only pages
    """
    
    # URLs that teachers should be redirected from
    REDIRECT_PATTERNS = [
        r'^/$',  # Home page
        r'^/courses/$',  # Public course list (optional)
    ]
    
    # URLs that are exempt from redirection
    EXEMPT_PATTERNS = [
        r'^/admin/',
        r'^/api/',
        r'^/accounts/',
        r'^/users/',
        r'^/courses/teacher/',
        r'^/payments/',
        r'^/static/',
        r'^/media/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.redirect_patterns = [re.compile(pattern) for pattern in self.REDIRECT_PATTERNS]
        self.exempt_patterns = [re.compile(pattern) for pattern in self.EXEMPT_PATTERNS]
    
    def __call__(self, request):
        # Check if user is authenticated and is a teacher
        if (request.user.is_authenticated and 
            hasattr(request.user, 'is_teacher') and 
            request.user.is_teacher):
            
            path = request.path
            
            # Check if path should be redirected
            should_redirect = any(pattern.match(path) for pattern in self.redirect_patterns)
            
            # Check if path is exempt
            is_exempt = any(pattern.match(path) for pattern in self.exempt_patterns)
            
            # Redirect to teacher dashboard if conditions are met
            if should_redirect and not is_exempt:
                return redirect('users:teacher_dashboard')
        
        response = self.get_response(request)
        return response
