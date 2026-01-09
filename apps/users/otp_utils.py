"""
OTP Utilities for Email-based OTP Authentication

This module provides utility functions for:
- Creating and managing OTP devices
- Sending OTP via email
- Verifying OTP tokens
- Rate limiting and security features
"""

import random
import string
import logging
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from django_otp.plugins.otp_email.models import EmailDevice

logger = logging.getLogger(__name__)
User = get_user_model()

# ==================== CONFIGURATION ====================

OTP_LENGTH = 6
OTP_VALIDITY_MINUTES = 5
MAX_OTP_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
MAX_RESEND_PER_HOUR = 5


# ==================== OTP DEVICE MANAGEMENT ====================

def get_or_create_email_device(user, purpose: str = 'verification') -> EmailDevice:
    """
    Get or create an EmailDevice for the user.
    
    Args:
        user: The user object
        purpose: Purpose of OTP (verification, login, password_reset)
    
    Returns:
        EmailDevice instance
    """
    device_name = f'otp_{purpose}_{user.pk}'
    
    # Delete any existing devices for this purpose
    EmailDevice.objects.filter(user=user, name__startswith=f'otp_{purpose}_').delete()
    
    # Create new device
    device = EmailDevice.objects.create(
        user=user,
        name=device_name,
        email=user.email,
        confirmed=False
    )
    
    return device


def generate_otp_token() -> str:
    """Generate a 6-digit numeric OTP token."""
    return ''.join(random.choices(string.digits, k=OTP_LENGTH))


def send_otp_email(user, purpose: str = 'verification') -> Tuple[bool, str, Optional[EmailDevice]]:
    """
    Generate and send OTP to user's email.
    
    Args:
        user: User object
        purpose: Purpose of OTP
    
    Returns:
        Tuple of (success, message, device)
    """
    # Check rate limiting for resend
    rate_limit_key = f'otp_resend_{user.pk}_{purpose}'
    resend_count = cache.get(rate_limit_key, 0)
    
    if resend_count >= MAX_RESEND_PER_HOUR:
        return False, 'Too many OTP requests. Please try again later.', None
    
    # Check cooldown
    cooldown_key = f'otp_cooldown_{user.pk}_{purpose}'
    if cache.get(cooldown_key):
        return False, f'Please wait {RESEND_COOLDOWN_SECONDS} seconds before requesting a new OTP.', None
    
    try:
        # Create or get device
        device = get_or_create_email_device(user, purpose)
        
        # Generate OTP token
        otp_token = generate_otp_token()
        
        # Store the token in the device (using the token field)
        device.token = otp_token
        device.valid_until = timezone.now() + timedelta(minutes=OTP_VALIDITY_MINUTES)
        device.confirmed = False
        device.save()
        
        # Prepare email context
        context = {
            'user': user,
            'otp_code': otp_token,
            'validity_minutes': OTP_VALIDITY_MINUTES,
            'purpose': purpose,
            'site_name': getattr(settings, 'SITE_NAME', 'LearnQuick'),
            'current_year': timezone.now().year,
        }
        
        # Render email templates (using unified template)
        subject = _get_otp_email_subject(purpose)
        html_message = render_to_string('account/otp/email/otp_email.html', context)
        plain_message = render_to_string('account/otp/email/otp_email.txt', context)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        # Update rate limiting
        cache.set(rate_limit_key, resend_count + 1, 3600)  # 1 hour
        cache.set(cooldown_key, True, RESEND_COOLDOWN_SECONDS)
        
        # Reset attempt counter
        attempt_key = f'otp_attempts_{user.pk}_{purpose}'
        cache.delete(attempt_key)
        
        logger.info(f'OTP sent to {user.email} for {purpose}')
        return True, 'OTP sent successfully to your email.', device
        
    except Exception as e:
        logger.error(f'Failed to send OTP to {user.email}: {str(e)}')
        return False, 'Failed to send OTP. Please try again.', None


def _get_otp_email_subject(purpose: str) -> str:
    """Get email subject based on purpose."""
    subjects = {
        'verification': 'Verify Your Email - LeQ',
        'login': 'Login Verification Code - LeQ',
        'password_reset': 'Password Reset Code - LeQ',
    }
    return subjects.get(purpose, 'Your OTP Code - LeQ')


# ==================== OTP VERIFICATION ====================

def verify_otp(user, otp_code: str, purpose: str = 'verification') -> Tuple[bool, str]:
    """
    Verify OTP token for a user.
    
    Args:
        user: User object
        otp_code: The OTP code entered by user
        purpose: Purpose of OTP
    
    Returns:
        Tuple of (success, message)
    """
    attempt_key = f'otp_attempts_{user.pk}_{purpose}'
    attempts = cache.get(attempt_key, 0)
    
    # Check if user is blocked due to too many attempts
    if attempts >= MAX_OTP_ATTEMPTS:
        block_key = f'otp_blocked_{user.pk}_{purpose}'
        if not cache.get(block_key):
            cache.set(block_key, True, 900)  # Block for 15 minutes
        return False, 'Too many incorrect attempts. Please request a new OTP after 15 minutes.'
    
    try:
        # Find the device
        device = EmailDevice.objects.filter(
            user=user,
            name__startswith=f'otp_{purpose}_',
            confirmed=False
        ).first()
        
        if not device:
            return False, 'No active OTP found. Please request a new one.'
        
        # Check if OTP has expired
        if device.valid_until and device.valid_until < timezone.now():
            device.delete()
            return False, 'OTP has expired. Please request a new one.'
        
        # Verify the token
        if device.token and device.token == otp_code:
            # OTP is valid - mark as confirmed and delete
            device.confirmed = True
            device.save()
            
            # Clear attempt counter
            cache.delete(attempt_key)
            
            # Delete the device after successful verification
            device.delete()
            
            logger.info(f'OTP verified for {user.email} ({purpose})')
            return True, 'OTP verified successfully.'
        else:
            # Increment attempt counter
            cache.set(attempt_key, attempts + 1, 1800)  # 30 minutes
            remaining = MAX_OTP_ATTEMPTS - attempts - 1
            return False, f'Invalid OTP. {remaining} attempts remaining.'
            
    except Exception as e:
        logger.error(f'OTP verification error for {user.email}: {str(e)}')
        return False, 'Verification failed. Please try again.'


# ==================== CLEANUP UTILITIES ====================

def cleanup_expired_otp_devices():
    """
    Remove all expired OTP devices.
    Can be called from a Celery task or management command.
    """
    expired_devices = EmailDevice.objects.filter(
        valid_until__lt=timezone.now(),
        confirmed=False
    )
    count = expired_devices.count()
    expired_devices.delete()
    logger.info(f'Cleaned up {count} expired OTP devices')
    return count


def delete_user_otp_devices(user, purpose: Optional[str] = None):
    """
    Delete all OTP devices for a user, optionally filtered by purpose.
    
    Args:
        user: User object
        purpose: Optional purpose filter
    """
    queryset = EmailDevice.objects.filter(user=user)
    if purpose:
        queryset = queryset.filter(name__startswith=f'otp_{purpose}_')
    queryset.delete()


# ==================== SESSION HELPERS ====================

def set_otp_verified_session(request, purpose: str = 'login'):
    """
    Mark OTP as verified in session.
    
    Args:
        request: HTTP request object
        purpose: Purpose of verification
    """
    request.session[f'otp_verified_{purpose}'] = True
    request.session[f'otp_verified_{purpose}_at'] = timezone.now().isoformat()


def is_otp_verified_session(request, purpose: str = 'login') -> bool:
    """
    Check if OTP has been verified in current session.
    
    Args:
        request: HTTP request object
        purpose: Purpose of verification
    
    Returns:
        True if OTP was verified
    """
    return request.session.get(f'otp_verified_{purpose}', False)


def clear_otp_session(request, purpose: str = 'login'):
    """
    Clear OTP verification from session.
    
    Args:
        request: HTTP request object
        purpose: Purpose of verification
    """
    request.session.pop(f'otp_verified_{purpose}', None)
    request.session.pop(f'otp_verified_{purpose}_at', None)


# ==================== USER STATE HELPERS ====================

def get_pending_user_from_session(request):
    """
    Get the user waiting for OTP verification from session.
    
    Returns:
        User instance or None if not found.
    """
    user_pk = request.session.get('otp_pending_user_pk')
    if user_pk:
        try:
            return User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            pass
    return None


def set_pending_user_session(request, user):
    """
    Store user PK in session for pending OTP verification.
    """
    request.session['otp_pending_user_pk'] = user.pk


def clear_pending_user_session(request):
    """
    Clear pending user from session.
    """
    request.session.pop('otp_pending_user_pk', None)
