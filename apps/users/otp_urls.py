"""
URL configuration for OTP-based authentication.

These URLs override allauth's default authentication to add OTP verification.
"""

from django.urls import path

from .otp_views import (
    OTPSignupView,
    OTPLoginView,
    OTPVerifyView,
    ResendOTPView,
    ForgotPasswordView,
    SetNewPasswordView,
    OTPLogoutView,
)

app_name = 'otp'

urlpatterns = [
    # Override allauth signup/login with OTP versions
    path('signup/', OTPSignupView.as_view(), name='signup'),
    path('login/', OTPLoginView.as_view(), name='login'),
    path('logout/', OTPLogoutView.as_view(), name='logout'),
    
    # OTP verification
    path('verify/', OTPVerifyView.as_view(), name='verify'),
    path('resend/', ResendOTPView.as_view(), name='resend'),
    
    # Password reset via OTP
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/', SetNewPasswordView.as_view(), name='reset_password'),
]
