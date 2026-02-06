"""
URL configuration for Mobile API
All endpoints for the React Native mobile app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # Authentication
    LoginView, RegisterView, LogoutView, ChangePasswordView,
    ForgotPasswordView, VerifyResetOTPView, ResetPasswordView,
    VerifySignupOTPView, ResendSignupOTPView,
    # User Profile
    UserProfileView, UserSettingsView,
    # Courses
    CategoryViewSet, CourseViewSet, LessonViewSet,
    # Enrollments & Progress
    EnrollmentViewSet,
    # Reviews
    ReviewViewSet,
    # Notifications
    NotificationViewSet,
    # Payments & Subscriptions
    PaymentViewSet, SubscriptionViewSet,
    # Analytics
    ListeningSessionViewSet, UserStatsView,
    # Banners
    BannerViewSet,
    # Certificates
    CertificateViewSet,
    # Downloads
    DownloadViewSet,
    # Search & Discovery
    SearchView, DashboardView,
)

# Initialize router
router = DefaultRouter()

# Register ViewSets
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'listening-sessions', ListeningSessionViewSet, basename='listening-session')
router.register(r'banners', BannerViewSet, basename='banner')
router.register(r'certificates', CertificateViewSet, basename='certificate')
router.register(r'downloads', DownloadViewSet, basename='download')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/verify-signup-otp/', VerifySignupOTPView.as_view(), name='verify-signup-otp'),
    path('auth/resend-signup-otp/', ResendSignupOTPView.as_view(), name='resend-signup-otp'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/verify-reset-otp/', VerifyResetOTPView.as_view(), name='verify-reset-otp'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    
    # User profile
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('settings/', UserSettingsView.as_view(), name='settings'),
    
    # Analytics & Stats
    path('stats/', UserStatsView.as_view(), name='user-stats'),
    
    # Search & Discovery
    path('search/', SearchView.as_view(), name='search'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]

"""
Mobile API Endpoints Summary:

AUTHENTICATION:
- POST   /api/mobile/auth/login/            - User login
- POST   /api/mobile/auth/register/         - User registration
- POST   /api/mobile/auth/logout/           - User logout
- POST   /api/mobile/auth/change-password/  - Change password

USER PROFILE:
- GET    /api/mobile/profile/               - Get user profile
- PATCH  /api/mobile/profile/               - Update user profile
- GET    /api/mobile/stats/                 - Get user statistics

CATEGORIES:
- GET    /api/mobile/categories/            - List all categories
- GET    /api/mobile/categories/{id}/       - Get category details

COURSES:
- GET    /api/mobile/courses/               - List all courses (filterable, searchable)
- GET    /api/mobile/courses/{id}/          - Get course details
- GET    /api/mobile/courses/featured/      - Get featured courses
- GET    /api/mobile/courses/trending/      - Get trending courses
- GET    /api/mobile/courses/top-rated/     - Get top-rated courses
- GET    /api/mobile/courses/{id}/reviews/  - Get course reviews
- POST   /api/mobile/courses/{id}/enroll/   - Enroll in course

LESSONS:
- GET    /api/mobile/lessons/               - List lessons
- GET    /api/mobile/lessons/{id}/          - Get lesson details
- POST   /api/mobile/lessons/{id}/update-progress/ - Update lesson progress

ENROLLMENTS:
- GET    /api/mobile/enrollments/           - List user's enrollments
- GET    /api/mobile/enrollments/{id}/      - Get enrollment details
- GET    /api/mobile/enrollments/active/    - Get active enrollments
- GET    /api/mobile/enrollments/completed/ - Get completed enrollments

REVIEWS:
- GET    /api/mobile/reviews/               - List user's reviews
- POST   /api/mobile/reviews/               - Create review
- GET    /api/mobile/reviews/{id}/          - Get review details
- PUT    /api/mobile/reviews/{id}/          - Update review
- DELETE /api/mobile/reviews/{id}/          - Delete review

NOTIFICATIONS:
- GET    /api/mobile/notifications/         - List notifications
- GET    /api/mobile/notifications/unread/  - Get unread notifications
- POST   /api/mobile/notifications/{id}/mark-read/ - Mark as read
- POST   /api/mobile/notifications/mark-all-read/  - Mark all as read

PAYMENTS:
- GET    /api/mobile/payments/              - List user's payments
- GET    /api/mobile/payments/{id}/         - Get payment details

SUBSCRIPTIONS:
- GET    /api/mobile/subscriptions/         - List user's subscriptions
- GET    /api/mobile/subscriptions/{id}/    - Get subscription details

LISTENING SESSIONS:
- GET    /api/mobile/listening-sessions/    - List listening sessions
- POST   /api/mobile/listening-sessions/    - Create listening session
- GET    /api/mobile/listening-sessions/{id}/ - Get session details

BANNERS:
- GET    /api/mobile/banners/               - List active banners
- GET    /api/mobile/banners/home/          - Get home page banners

SEARCH & DISCOVERY:
- GET    /api/mobile/search/?q=query        - Search courses
- GET    /api/mobile/dashboard/             - Get dashboard data

FILTERING & ORDERING:
Courses support filtering by:
- category, level, is_free, is_featured, teacher
Courses support ordering by:
- created_at, price, average_rating, total_enrollments
Courses support searching by:
- title, description, short_description

Example Usage:
- GET /api/mobile/courses/?category=1&level=beginner&ordering=-average_rating
- GET /api/mobile/courses/?search=python&is_free=true
"""

