"""
Django settings for leq project - Audio Learning Platform
"""

from pathlib import Path
import os
from datetime import timedelta
import environ
from django.templatetags.static import static
from django.urls import reverse_lazy

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Read environment files
# Prefer local overrides in `.env.local` for development, fall back to `.env`.
local_env = os.path.join(BASE_DIR, '.env.local')
prod_env = os.path.join(BASE_DIR, '.env')
if os.path.exists(local_env):
    environ.Env.read_env(local_env)
    print("DEBUG: Loaded environment from .env.local")
elif os.path.exists(prod_env):
    environ.Env.read_env(prod_env)
    print("DEBUG: Loaded environment from .env")
else:
    # No env file found; rely on OS-level environment variables
    print("DEBUG: No .env file found; relying on OS environment variables")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-otu^*u_&!zzks2%kg2)*q47-mto1+=l*%by4i!r5%%&^a&gwjw')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

SITE_URL = env('SITE_URL', default='http://localhost:8000')


# Application definition

INSTALLED_APPS = [
    # Unfold Admin disabled - using custom platformadmin
    # 'unfold',
    # 'unfold.contrib.filters',
    # 'unfold.contrib.forms',
    # 'unfold.contrib.import_export',
    
    # Django Core
    # 'django.contrib.admin',  # Disabled - using custom platformadmin at /platformadmin/
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'dj_rest_auth',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'dj_rest_auth.registration',
    'corsheaders',
    'django_celery_beat',
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',
    'drf_spectacular',
    'storages',
    
    # Django OTP for two-factor authentication
    'django_otp',
    'django_otp.plugins.otp_email',
    
    # Local apps
    'apps.users.apps.UsersConfig',
    'apps.courses.apps.CoursesConfig',
    'apps.audio.apps.AudioConfig',
    'apps.payments.apps.PaymentsConfig',
    'apps.analytics.apps.AnalyticsConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.common.apps.CommonConfig',
    'apps.platformadmin.apps.PlatformadminConfig',
    # Top-level API app (mobile API implementation)
    'mobileapi.apps.MobileApiConfig',
]

SITE_ID = 1


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files on shared hosting
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Django OTP middleware - must be after AuthenticationMiddleware
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    # Custom OTP verification middleware - must be after all auth middleware
    'apps.users.otp_middleware.OTPVerificationMiddleware',
    # Teacher redirect middleware - automatically redirect teachers to dashboard
    'apps.users.teacher_middleware.TeacherRedirectMiddleware',
]

ROOT_URLCONF = 'leq.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'apps.notifications.context_processors.unread_counts',
            ],
        },
    },
]

WSGI_APPLICATION = 'leq.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# Support both MySQL (shared hosting) and SQLite (local development)
DB_ENGINE = env('DB_ENGINE', default='django.db.backends.mysql')

# When running on shared hosting it's common that building C extensions
# (like `mysqlclient`) fails. To avoid that, prefer a pure-Python
# alternative (`mysql-connector-python`) when `mysqlclient` is missing
# or reports a version older than Django's minimum requirement.
def _should_use_connector():
    """Check if we should use mysql-connector-python instead of mysqlclient."""
    try:
        # Try importing MySQLdb (provided by mysqlclient or PyMySQL)
        import MySQLdb
        ver = getattr(MySQLdb, '__version__', '0.0.0')
        
        # Parse version string and compare with Django's minimum (1.4.3)
        def _parse_version(version_str):
            parts = []
            for part in str(version_str).split('.'):
                try:
                    parts.append(int(part))
                except ValueError:
                    # Handle non-numeric parts by ignoring them
                    break
            return tuple(parts + [0] * (3 - len(parts)))  # pad to 3 elements
        
        current_ver = _parse_version(ver)
        min_ver = (1, 4, 3)
        
        if current_ver < min_ver:
            print(f"DEBUG: MySQLdb version {ver} < required 1.4.3, trying mysql-connector-python")
            return True
        else:
            print(f"DEBUG: MySQLdb version {ver} is acceptable")
            return False
            
    except ImportError:
        print("DEBUG: MySQLdb not available, trying mysql-connector-python")
        return True
    except Exception as e:
        print(f"DEBUG: Error checking MySQLdb: {e}, trying mysql-connector-python")
        return True

if DB_ENGINE == 'django.db.backends.mysql':
    # Default engine; may be overridden below if fallback driver chosen
    engine = 'django.db.backends.mysql'

    # If mysqlclient is missing or too old, try mysql-connector-python
    if _should_use_connector():
        try:
            import mysql.connector  # provided by mysql-connector-python
            engine = 'mysql.connector.django'
            print("DEBUG: Using mysql.connector.django backend")
        except ImportError:
            print("DEBUG: mysql.connector not available, falling back to django.db.backends.mysql")
            # Leave engine as django.db.backends.mysql; Django will raise
            # the original helpful error if nothing usable is available.
            pass

    DATABASES = {
        'default': {
            'ENGINE': engine,
            'NAME': env('DB_NAME', default=''),
            'USER': env('DB_USER', default=''),
            'PASSWORD': env('DB_PASSWORD', default=''),
            'HOST': env('DB_HOST', default='localhost'),
            'PORT': env('DB_PORT', default='3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'charset': 'utf8mb4',
            },
        }
    }
elif DB_ENGINE == 'django.db.backends.postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME', default=''),
            'USER': env('DB_USER', default=''),
            'PASSWORD': env('DB_PASSWORD', default=''),
            'HOST': env('DB_HOST', default='localhost'),
            'PORT': env('DB_PORT', default='5432'),
        }
    }
else:
    # SQLite for local development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / env('DB_NAME', default='db.sqlite3'),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Only include static dir if it exists (avoid warnings on fresh deploys)
if (BASE_DIR / 'static').exists():
    STATICFILES_DIRS = [BASE_DIR / 'static']
else:
    STATICFILES_DIRS = []

# WhiteNoise configuration for static files on shared hosting
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# ==================== AUTHENTICATION ====================

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Django Allauth Settings
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'none'  # We handle email verification via OTP
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# Custom allauth adapter for OTP integration
ACCOUNT_ADAPTER = 'apps.users.adapters.OTPAccountAdapter'

# Disable allauth's email confirmation (we use OTP instead)
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
ACCOUNT_CONFIRM_EMAIL_ON_GET = False

# Allow registration
ACCOUNT_ALLOW_REGISTRATION = True

# ==================== OTP CONFIGURATION ====================

# OTP Token settings
OTP_TOKEN_LENGTH = 6  # 6-digit OTP code
OTP_TOKEN_VALIDITY = 300  # 5 minutes in seconds

# OTP Security settings
OTP_MAX_ATTEMPTS = 5  # Block after 5 failed attempts
OTP_RESEND_COOLDOWN = 60  # Minimum 60 seconds between resends
OTP_LOCKOUT_DURATION = 900  # 15 minutes lockout after max attempts

# OTP Email settings
OTP_EMAIL_SUBJECT_SIGNUP = 'Verify your email - LearnQuick'
OTP_EMAIL_SUBJECT_LOGIN = 'Login verification code - LearnQuick'
OTP_EMAIL_SUBJECT_PASSWORD_RESET = 'Password reset code - LearnQuick'

# Session keys for OTP
OTP_SESSION_PENDING_USER = 'otp_pending_user_id'
OTP_SESSION_PURPOSE = 'otp_purpose'
OTP_SESSION_VERIFIED = 'otp_verified'
OTP_SESSION_VERIFIED_TIME = 'otp_verified_time'
OTP_SESSION_LAST_RESEND = 'otp_last_resend'

# URLs that don't require OTP verification
OTP_EXEMPT_URLS = [
    '/accounts/signup/',
    '/accounts/login/',
    '/accounts/logout/',
    '/users/verify-otp/',
    '/users/resend-otp/',
    '/users/forgot-password/',
    '/users/reset-password/',
    '/users/otp/',
    '/admin/',
    '/api/',
    '/static/',
    '/media/',
    '/',
]

# ==================== REST FRAMEWORK ====================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',  # For mobile API
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'login': '5/min',  # Rate limit login attempts
    },
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# DRF Spectacular (API Documentation)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Audio Learning Platform API',
    'DESCRIPTION': 'API for audio-based learning platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ==================== CORS ====================

# Allow mobile app origins (update these in production)
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:19006',  # Expo default web port
    'http://localhost:19000',  # Expo Metro bundler
])

# For development, allow all origins (disable in production)
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=DEBUG)

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[
    'http://localhost:8000',
    'http://127.0.0.1:8000',
])

# ==================== CLOUDFLARE R2 STORAGE ====================

USE_S3 = env.bool('USE_S3', default=False)

if USE_S3:
    # Cloudflare R2 settings
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL')
    AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='auto')
    AWS_S3_SIGNATURE_VERSION = env('AWS_S3_SIGNATURE_VERSION', default='s3v4')
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600  # 1 hour
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    
    # Storage backends
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3StaticStorage'

# ==================== RAZORPAY ====================

RAZORPAY_KEY_ID = env('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = env('RAZORPAY_KEY_SECRET', default='')
RAZORPAY_WEBHOOK_SECRET = env('RAZORPAY_WEBHOOK_SECRET', default='')

# ==================== CELERY ====================

CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ==================== EMAIL ====================

# Core SMTP settings (read from .env)
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

# Enable SMTP only when explicitly requested and credentials are provided
USE_SMTP = env.bool('USE_SMTP', default=False)
# Check credentials presence
_SMTP_CREDENTIALS_PRESENT = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)

if USE_SMTP and _SMTP_CREDENTIALS_PRESENT:
    # Use SMTP backend when credentials are available
    EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
    DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
    SERVER_EMAIL = env('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)
    ACCOUNT_DEFAULT_FROM_EMAIL = env('ACCOUNT_DEFAULT_FROM_EMAIL', default=DEFAULT_FROM_EMAIL)
elif USE_SMTP and not _SMTP_CREDENTIALS_PRESENT:
    # If the developer intentionally enabled SMTP but didn't provide credentials,
    # fall back to console backend to avoid sending with a mismatched sender.
    import warnings
    warnings.warn(
        'USE_SMTP is True but EMAIL_HOST_USER/EMAIL_HOST_PASSWORD are not set. '
        'Falling back to console email backend to avoid SMTP sender errors.'
    )
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'no-reply@localhost'
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
    ACCOUNT_DEFAULT_FROM_EMAIL = DEFAULT_FROM_EMAIL
else:
    # Default to console backend for development when SMTP not explicitly enabled
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'no-reply@localhost'
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
    ACCOUNT_DEFAULT_FROM_EMAIL = DEFAULT_FROM_EMAIL

# ==================== CRISPY FORMS ====================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"



# ==================== SECURITY SETTINGS ====================

if not DEBUG:
    # SSL/HTTPS settings (enable after SSL certificate is configured on Domainz)
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
    SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
    CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=False)
    
    # Always enable these security headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # HSTS settings (enable only after SSL is working)
    if env.bool('ENABLE_HSTS', default=False):
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True

# ==================== LOGGING ====================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# ==================== AUDIO SETTINGS ====================

# Maximum audio file size (100MB)
MAX_AUDIO_FILE_SIZE = 100 * 1024 * 1024

# Allowed audio formats
ALLOWED_AUDIO_FORMATS = ['mp3', 'm4a', 'wav', 'aac']

# Presigned URL expiry time (in seconds)
AUDIO_URL_EXPIRY = 3600  # 1 hour

