"""
URL configuration for users app
"""
from django.urls import path, include
from . import views
from . import otp_views
from . import student_views

app_name = 'users'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    
    # Profile
    path('profile/', views.ProfileDetailView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('profile/student/edit/', views.update_student_profile, name='student_profile_update'),
    path('profile/teacher/edit/', views.update_teacher_profile, name='teacher_profile_update'),
    
    # Teacher Settings
    path('teacher/settings/', views.teacher_settings, name='teacher_settings'),
    
    # Student-Specific Features
    path('student/goals/', student_views.student_learning_goals, name='student_learning_goals'),
    path('student/billing/', student_views.student_billing_history, name='student_billing'),
    path('student/achievements/', student_views.student_achievements, name='student_achievements'),
    
    # Address Management
    path('addresses/', views.manage_addresses, name='manage_addresses'),
    path('addresses/<int:address_id>/delete/', views.delete_address, name='delete_address'),
    path('addresses/<int:address_id>/set-default/', views.set_default_address, name='set_default_address'),
    
    # Public Teacher Profile
    path('teacher/<int:teacher_id>/', views.teacher_public_profile, name='teacher_public_profile'),
    
    # Logout (OTP-aware logout)
    path('logout/', otp_views.OTPLogoutView.as_view(), name='logout'),
    
    # OTP Authentication URLs
    path('otp/', include('apps.users.otp_urls', namespace='otp')),
    
    # Direct OTP verification access (for convenience)
    path('verify-otp/', otp_views.OTPVerifyView.as_view(), name='otp_verify'),
    path('resend-otp/', otp_views.ResendOTPView.as_view(), name='otp_resend'),
    path('forgot-password/', otp_views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/', otp_views.SetNewPasswordView.as_view(), name='reset_password'),
]
