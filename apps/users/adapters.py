"""
Custom Allauth Adapter for OTP-based authentication.

This adapter overrides default allauth behavior to integrate with our OTP system.
"""

from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.utils import user_email
from django.urls import reverse


class OTPAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter that integrates allauth with our OTP system.
    
    Key customizations:
    - Users are created as inactive by default
    - Email verification happens via OTP instead of link
    - Login requires OTP verification
    """
    
    def save_user(self, request, user, form, commit=True):
        """
        Save user and set as inactive until OTP is verified.
        """
        user = super().save_user(request, user, form, commit=False)
        
        # Set user as inactive - will be activated after OTP verification
        user.is_active = False
        
        if commit:
            user.save()
        
        return user
    
    def confirm_email(self, request, email_address):
        """
        Override email confirmation to use our OTP system.
        We don't use allauth's email confirmation links.
        """
        # Mark email as verified
        email_address.verified = True
        email_address.set_as_primary(conditional=True)
        email_address.save()
        
        # Also update our custom field
        user = email_address.user
        user.email_verified = True
        user.is_active = True
        user.save(update_fields=['email_verified', 'is_active'])
    
    def is_open_for_signup(self, request):
        """
        Check if registration is open.
        Can be controlled via settings.
        """
        return getattr(settings, 'ACCOUNT_ALLOW_REGISTRATION', True)
    
    def get_login_redirect_url(self, request):
        """
        Get the URL to redirect to after login.
        - Prefer the `next` parameter if present (from GET/POST).
        - If the logged-in user is a platform admin, default to the platformadmin dashboard.
        - Otherwise fall back to `settings.LOGIN_REDIRECT_URL`.
        """
        # Respect explicit next parameter (preserve return-to behavior)
        next_url = None
        if request is not None:
            next_url = request.POST.get('next') or request.GET.get('next')

        if next_url:
            return next_url

        # If user is authenticated and a platform admin, send them to platformadmin dashboard
        user = getattr(request, 'user', None)
        if user and getattr(user, 'is_authenticated', False):
            try:
                if getattr(user, 'role', '') == 'admin' and getattr(user, 'is_staff', False):
                    return reverse('platformadmin:dashboard')
            except Exception:
                pass

        return settings.LOGIN_REDIRECT_URL
    
    def pre_login(
        self,
        request,
        user,
        *,
        email_verification=None,
        signal_kwargs=None,
        email=None,
        signup=False,
        redirect_url=None
    ):
        """
        Override to prevent automatic login - we need OTP verification first.
        """
        # Skip the standard email verification (we use OTP instead)
        # Return None to allow login to proceed
        # The actual login flow is handled by our custom views
        return None
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Override to NOT send allauth's confirmation email.
        We send OTP instead via our custom views.
        """
        # Don't send allauth's confirmation email
        # OTP is sent by our custom signup view
        pass
    
    def respond_email_verification_sent(self, request, user):
        """
        Redirect to our OTP verification page instead of allauth's page.
        """
        return redirect('users:otp_verify')
    
    def add_message(
        self,
        request,
        level,
        message_template,
        message_context=None,
        extra_tags=""
    ):
        """
        Override to customize messages if needed.
        """
        # Filter out certain allauth messages that don't apply to OTP flow
        skip_messages = [
            'account/messages/email_confirmation_sent.txt',
            'account/messages/logged_in.txt',
        ]
        
        if message_template in skip_messages:
            return
        
        super().add_message(request, level, message_template, message_context, extra_tags)
