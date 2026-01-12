"""
URL configuration for leq project - Audio Learning Platform
"""
# from django.contrib import admin  # Disabled - using custom platformadmin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from api.home_views import home_view

# Import OTP views to override allauth defaults
from apps.users.otp_views import (
    OTPSignupView,
    OTPLoginView,
    OTPLogoutView,
)

# Django admin disabled - using custom platformadmin instead
# admin.site.site_header = "Audio Learning Platform Admin"
# admin.site.site_title = "ALP Admin"
# admin.site.index_title = "Welcome to Audio Learning Platform Admin"

urlpatterns = [
    # Admin (disabled - use /platformadmin/ instead)
    # path('admin/', admin.site.urls),
    
    # Platform Admin (Custom Admin Dashboard)
    path('platformadmin/', include('apps.platformadmin.urls')),
    
    # Platform Admin REST API (for automation & external integrations)
    path('api/admin/', include('apps.platformadmin.api_urls')),
    
    # OTP Authentication - Override allauth's signup/login BEFORE including allauth.urls
    path('accounts/signup/', OTPSignupView.as_view(), name='account_signup'),
    path('accounts/login/', OTPLoginView.as_view(), name='account_login'),
    path('accounts/logout/', OTPLogoutView.as_view(), name='account_logout'),
    
    # Authentication (django-allauth) - for other allauth features
    path('accounts/', include('allauth.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # API endpoints
    path('api/v1/', include('api.urls')),
    
    # Mobile API endpoints
    path('api/mobile/', include('mobileapi.urls')),
    
    # Web views
    path('', home_view, name='home'),
    path('users/', include('apps.users.urls')),
    path('courses/', include('apps.courses.urls')),
    path('payments/', include('apps.payments.urls')),
    path('notifications/', include('apps.notifications.urls')),
]


if not getattr(settings, 'USE_S3', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Static files are handled by WhiteNoise in production; still add during DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)