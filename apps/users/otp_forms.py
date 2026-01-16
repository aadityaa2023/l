"""
OTP Authentication Forms

Custom forms for:
- Signup with OTP verification
- Login with OTP
- OTP verification
- Password reset via OTP
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from allauth.account.forms import SignupForm as AllauthSignupForm
from allauth.account.forms import LoginForm as AllauthLoginForm

User = get_user_model()


# ==================== OTP VERIFICATION FORM ====================

class OTPVerificationForm(forms.Form):
    """
    Form for verifying OTP code.
    """
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label=_('OTP Code'),
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': 'Enter 6-digit OTP',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'autofocus': True,
        }),
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message=_('OTP must be exactly 6 digits.')
            )
        ],
        help_text=_('Enter the 6-digit code sent to your email.')
    )
    
    def clean_otp_code(self):
        otp = self.cleaned_data.get('otp_code', '').strip()
        if not otp.isdigit():
            raise forms.ValidationError(_('OTP must contain only numbers.'))
        if len(otp) != 6:
            raise forms.ValidationError(_('OTP must be exactly 6 digits.'))
        return otp


# ==================== CUSTOM SIGNUP FORM ====================

class OTPSignupForm(AllauthSignupForm):
    """
    Custom signup form that integrates with OTP verification.
    Extends allauth's SignupForm.
    """
    first_name = forms.CharField(
        max_length=150,
        required=False,
        label=_('First Name'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name',
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label=_('Last Name'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name',
        })
    )
    
    phone = forms.CharField(
        max_length=15,
        required=True,
        label=_('Phone Number'),
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'XXXXXXXXXX',
            'pattern': r'[0-9]{10}',
        }),
        help_text=_('Enter a 10-digit mobile number (e.g. 9876543210)')
    )
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise forms.ValidationError(_('Phone number is required.'))
        # Only allow exactly 10 digits (no country prefix)
        if len(phone) != 10:
            raise forms.ValidationError(_('Phone number must contain exactly 10 digits.'))
        if not phone.isdigit():
            raise forms.ValidationError(_('Phone number must contain only digits.'))
        return phone
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize field widgets
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.update({
                'class': 'form-control',
                'placeholder': 'Email address',
            })
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs.update({
                'class': 'form-control',
                'placeholder': 'Create password',
            })
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({
                'class': 'form-control',
                'placeholder': 'Confirm password',
            })
    
    def save(self, request):
        """
        Save user as INACTIVE - will be activated after OTP verification.
        """
        user = super().save(request)
        
        # Set additional fields
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.phone = self.cleaned_data.get('phone', '')
        
        # Create user as INACTIVE - activated after OTP verification
        user.is_active = False
        user.save()
        
        return user


# ==================== CUSTOM LOGIN FORM ====================

class OTPLoginForm(AllauthLoginForm):
    """
    Custom login form that will trigger OTP verification after password check.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize field widgets
        if 'login' in self.fields:
            self.fields['login'].widget.attrs.update({
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter your email',
            })
        if 'password' in self.fields:
            self.fields['password'].widget.attrs.update({
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter your password',
            })


# ==================== PASSWORD RESET FORMS ====================

class ForgotPasswordEmailForm(forms.Form):
    """
    Form to enter email for password reset via OTP.
    """
    email = forms.EmailField(
        label=_('Email Address'),
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email',
            'autofocus': True,
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not User.objects.filter(email=email).exists():
            # Don't reveal whether email exists for security
            # But we need to handle this in the view
            pass
        return email


class OTPPasswordResetForm(SetPasswordForm):
    """
    Form for setting new password after OTP verification.
    Extends Django's SetPasswordForm.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize field widgets
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'New password',
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Confirm new password',
        })


# ==================== RESEND OTP FORM ====================

class ResendOTPForm(forms.Form):
    """
    Form for resending OTP - mostly for CSRF protection.
    """
    pass
