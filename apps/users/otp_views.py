"""
OTP Authentication Views

Views for:
- Signup with OTP verification (required)
- Login without OTP (direct login after password)
- OTP verification page (for signup and password reset)
- Resend OTP
- Password reset via OTP
"""

import logging

from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponseRedirect
from django.conf import settings

from allauth.account.views import SignupView as AllauthSignupView
from allauth.account.views import LoginView as AllauthLoginView
from allauth.account.utils import complete_signup
from allauth.account import app_settings as allauth_settings

from .otp_forms import (
    OTPVerificationForm,
    OTPSignupForm,
    OTPLoginForm,
    ForgotPasswordEmailForm,
    OTPPasswordResetForm,
    ResendOTPForm,
)
from .otp_utils import (
    send_otp_email,
    verify_otp,
    set_pending_user_session,
    get_pending_user_from_session,
    clear_pending_user_session,
    set_otp_verified_session,
    is_otp_verified_session,
    clear_otp_session,
    delete_user_otp_devices,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== SIGNUP WITH OTP ====================

@method_decorator([csrf_protect, never_cache], name='dispatch')
class OTPSignupView(AllauthSignupView):
    """
    Custom signup view that creates inactive user and sends OTP.
    
    Flow:
    1. User fills signup form
    2. User is created as inactive
    3. OTP is sent to email
    4. User is redirected to OTP verification page
    5. After OTP verification, user is activated
    """
    template_name = 'account/otp/signup.html'
    form_class = OTPSignupForm
    
    def form_valid(self, form):
        """
        Override to create inactive user and send OTP.
        """
        # Create user (inactive by default in our custom form)
        user = form.save(self.request)
        
        # Send OTP
        success, message, device = send_otp_email(user, purpose='verification')
        
        if success:
            # Store user PK in session for verification
            set_pending_user_session(self.request, user)
            self.request.session['otp_purpose'] = 'verification'
            
            messages.success(self.request, f'Account created! {message}')
            return redirect('users:otp_verify')
        else:
            # If OTP sending failed, still redirect but show error
            set_pending_user_session(self.request, user)
            self.request.session['otp_purpose'] = 'verification'
            
            messages.warning(self.request, f'Account created but {message}')
            return redirect('users:otp_verify')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create Account'
        return context


# ==================== LOGIN WITH OTP ====================

@method_decorator([csrf_protect, never_cache], name='dispatch')
class OTPLoginView(AllauthLoginView):
    """
    Custom login view that logs in user directly after password validation.
    OTP is only required during signup for email verification.
    
    Flow:
    1. User enters email/password
    2. If credentials valid, log user in directly
    3. No OTP verification required for login
    """
    template_name = 'account/otp/login.html'
    form_class = OTPLoginForm
    
    def form_valid(self, form):
        """
        Override to login user directly without OTP verification.
        """
        # Get the user from the form
        user = form.user
        
        # Check if user is active
        if not user.is_active:
            messages.error(self.request, 'Your account is not active. Please verify your email first.')
            return redirect('users:otp_verify')
        
        # Log the user in directly (no OTP required for login)
        auth_login(self.request, user, backend='allauth.account.auth_backends.AuthenticationBackend')
        
        messages.success(self.request, 'Login successful!')
        
        # Redirect platform admins to platformadmin dashboard
        if user.role == 'admin' and user.is_staff:
            return redirect('platformadmin:dashboard')
        
        # Default redirect for regular users
        return redirect(settings.LOGIN_REDIRECT_URL)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Login'
        return context


# ==================== OTP VERIFICATION ====================

@method_decorator([csrf_protect, never_cache], name='dispatch')
class OTPVerifyView(FormView):
    """
    View to verify OTP code.
    Handles verification for signup and password reset only.
    Login does not require OTP verification.
    """
    template_name = 'account/otp/verify_otp.html'
    form_class = OTPVerificationForm
    
    def dispatch(self, request, *args, **kwargs):
        """Check if there's a pending user for verification."""
        self.pending_user = get_pending_user_from_session(request)
        self.purpose = request.session.get('otp_purpose', 'verification')
        
        if not self.pending_user:
            messages.error(request, 'No pending verification. Please start again.')
            return redirect('account_login')
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Verify OTP and complete the appropriate action."""
        otp_code = form.cleaned_data['otp_code']
        
        success, message = verify_otp(self.pending_user, otp_code, self.purpose)
        
        if success:
            return self._handle_verification_success()
        else:
            messages.error(self.request, message)
            return self.form_invalid(form)
    
    def _handle_verification_success(self):
        """Handle successful OTP verification based on purpose."""
        purpose = self.purpose
        user = self.pending_user
        
        if purpose == 'verification':
            # Signup verification - activate user
            user.is_active = True
            user.email_verified = True
            user.save(update_fields=['is_active', 'email_verified'])
            
            # Clear session data
            clear_pending_user_session(self.request)
            
            # Log the user in
            auth_login(self.request, user, backend='allauth.account.auth_backends.AuthenticationBackend')
            
            messages.success(self.request, 'Email verified! Welcome to LeQ.')
            
            # Redirect platform admins to platformadmin dashboard
            if user.role == 'admin' and user.is_staff:
                return redirect('platformadmin:dashboard')
            
            # Default redirect for regular users
            return redirect(settings.LOGIN_REDIRECT_URL)
            
        elif purpose == 'password_reset':
            # Password reset - redirect to set new password
            set_otp_verified_session(self.request, 'password_reset')
            
            messages.success(self.request, 'OTP verified. Please set your new password.')
            return redirect('users:reset_password')
        
        return redirect('home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_user'] = self.pending_user
        context['purpose'] = self.purpose
        context['email'] = self.pending_user.email if self.pending_user else ''
        
        # Get purpose-specific title
        titles = {
            'verification': 'Verify Your Email',
            'password_reset': 'Verify Password Reset',
        }
        context['page_title'] = titles.get(self.purpose, 'Verify OTP')
        
        return context


# ==================== RESEND OTP ====================

@method_decorator([csrf_protect, never_cache], name='dispatch')
class ResendOTPView(View):
    """
    View to resend OTP code.
    """
    
    def post(self, request):
        """Handle OTP resend request."""
        pending_user = get_pending_user_from_session(request)
        purpose = request.session.get('otp_purpose', 'verification')
        
        if not pending_user:
            messages.error(request, 'No pending verification found.')
            return redirect('account_login')
        
        success, message, device = send_otp_email(pending_user, purpose=purpose)
        
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        
        return redirect('users:otp_verify')
    
    def get(self, request):
        """Redirect GET requests to verification page."""
        return redirect('users:otp_verify')


# ==================== FORGOT PASSWORD WITH OTP ====================

@method_decorator([csrf_protect, never_cache], name='dispatch')
class ForgotPasswordView(FormView):
    """
    First step of password reset: enter email to receive OTP.
    """
    template_name = 'account/otp/forgot_password.html'
    form_class = ForgotPasswordEmailForm
    
    def form_valid(self, form):
        """Send OTP to the email address."""
        email = form.cleaned_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Send OTP
            success, message, device = send_otp_email(user, purpose='password_reset')
            
            if success:
                set_pending_user_session(self.request, user)
                self.request.session['otp_purpose'] = 'password_reset'
                
                messages.success(self.request, message)
                return redirect('users:otp_verify')
            else:
                messages.error(self.request, message)
                return self.form_invalid(form)
                
        except User.DoesNotExist:
            # Don't reveal that email doesn't exist (security)
            messages.info(
                self.request, 
                'If an account with this email exists, you will receive an OTP.'
            )
            return redirect('account_login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Forgot Password'
        return context


@method_decorator([csrf_protect, never_cache], name='dispatch')
class SetNewPasswordView(FormView):
    """
    Final step: set new password after OTP verification.
    """
    template_name = 'account/otp/set_new_password.html'
    form_class = OTPPasswordResetForm
    
    def dispatch(self, request, *args, **kwargs):
        """Verify that OTP was verified before allowing password change."""
        if not is_otp_verified_session(request, 'password_reset'):
            messages.error(request, 'Please verify OTP first.')
            return redirect('users:forgot_password')
        
        self.pending_user = get_pending_user_from_session(request)
        if not self.pending_user:
            messages.error(request, 'Session expired. Please start again.')
            return redirect('users:forgot_password')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Pass user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.pending_user
        return kwargs
    
    def form_valid(self, form):
        """Save the new password."""
        form.save()
        
        # Clear all session data
        clear_pending_user_session(self.request)
        clear_otp_session(self.request, 'password_reset')
        
        # Delete any remaining OTP devices
        delete_user_otp_devices(self.pending_user, 'password_reset')
        
        messages.success(self.request, 'Password changed successfully! Please login.')
        return redirect('account_login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Set New Password'
        return context


# ==================== LOGOUT ====================

class OTPLogoutView(View):
    """
    Logout view that clears any remaining session data.
    """
    
    def get(self, request):
        return self.post(request)
    
    def post(self, request):
        # Clear any pending OTP session data (from signup/password reset)
        clear_pending_user_session(request)
        
        # Perform logout
        auth_logout(request)
        
        messages.success(request, 'You have been logged out successfully.')
        return redirect('home')
