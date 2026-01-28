"""
Constants for Mobile API
"""

# API Version
API_VERSION = "1.0.0"

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Course Limits
FEATURED_COURSES_LIMIT = 10
TRENDING_COURSES_LIMIT = 10
TOP_RATED_COURSES_LIMIT = 10
RECOMMENDED_COURSES_LIMIT = 10

# Search
MAX_SEARCH_RESULTS = 50

# Dashboard
DASHBOARD_FEATURED_COURSES = 5
DASHBOARD_CATEGORIES = 10
DASHBOARD_BANNERS = 3
DASHBOARD_CONTINUE_LEARNING = 3

# Progress Tracking
MIN_LESSON_COMPLETION_PERCENTAGE = 95  # Consider lesson completed at 95%
PROGRESS_UPDATE_INTERVAL_SECONDS = 30  # Update progress every 30 seconds

# Session Management
SESSION_TIMEOUT_SECONDS = 3600  # 1 hour
MAX_CONCURRENT_SESSIONS = 3

# File Upload
MAX_PROFILE_PICTURE_SIZE_MB = 5
ALLOWED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'webp']

# Rating
MIN_RATING = 1
MAX_RATING = 5

# Review
MIN_REVIEW_LENGTH = 10
MAX_REVIEW_LENGTH = 1000

# Notification
MAX_NOTIFICATIONS_FETCH = 50
NOTIFICATION_RETENTION_DAYS = 90

# Error Messages
ERROR_MESSAGES = {
    'auth_required': 'Authentication required',
    'invalid_credentials': 'Invalid email or password',
    'account_inactive': 'Your account is inactive',
    'enrollment_required': 'You must be enrolled to access this content',
    'already_enrolled': 'You are already enrolled in this course',
    'invalid_token': 'Invalid or expired token',
    'permission_denied': 'You do not have permission to perform this action',
    'course_not_found': 'Course not found',
    'lesson_not_found': 'Lesson not found',
    'enrollment_not_found': 'Enrollment not found',
    'invalid_progress_data': 'Invalid progress data',
    'payment_required': 'Payment required to enroll in this course',
    'review_exists': 'You have already reviewed this course',
    'weak_password': 'Password must be at least 8 characters',
    'passwords_not_match': 'Passwords do not match',
}

# Success Messages
SUCCESS_MESSAGES = {
    'login_success': 'Successfully logged in',
    'logout_success': 'Successfully logged out',
    'registration_success': 'Account created successfully',
    'password_changed': 'Password changed successfully',
    'profile_updated': 'Profile updated successfully',
    'enrollment_created': 'Successfully enrolled in course',
    'progress_updated': 'Progress updated successfully',
    'review_created': 'Review submitted successfully',
    'review_updated': 'Review updated successfully',
    'notification_marked_read': 'Notification marked as read',
    'all_notifications_read': 'All notifications marked as read',
}

# HTTP Status Codes
STATUS_OK = 200
STATUS_CREATED = 201
STATUS_NO_CONTENT = 204
STATUS_BAD_REQUEST = 400
STATUS_UNAUTHORIZED = 401
STATUS_FORBIDDEN = 403
STATUS_NOT_FOUND = 404
STATUS_SERVER_ERROR = 500
