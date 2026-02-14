from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password"""
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with email as the unique identifier"""
    
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    )
    
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    phone = models.CharField(_('phone number'), max_length=15, blank=True)
    role = models.CharField(_('role'), max_length=10, choices=ROLE_CHOICES, default='student')
    
    is_staff = models.BooleanField(_('staff status'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    
    email_verified = models.BooleanField(_('email verified'), default=False)
    
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between"""
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user"""
        return self.first_name

    @property
    def is_teacher(self):
        return self.role == 'teacher'

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_free_user(self):
        """Check if user has free access to all paid courses"""
        if self.role != 'student':
            return False
        
        try:
            from apps.platformadmin.models import FreeUser
            free_user = FreeUser.objects.filter(user=self).first()
            return free_user.has_access() if free_user else False
        except Exception:
            return False
    
    def get_profile_picture_url(self):
        """Get the profile picture URL with cache busting"""
        try:
            # Check based on role first
            if self.is_student or self.role == 'student':
                profile = self.student_profile
                if profile and profile.profile_picture:
                    timestamp = int(profile.updated_at.timestamp())
                    return f"{profile.profile_picture.url}?v={timestamp}"
            
            if self.is_teacher or self.role == 'teacher':
                profile = self.teacher_profile
                if profile and profile.profile_picture:
                    timestamp = int(profile.updated_at.timestamp())
                    return f"{profile.profile_picture.url}?v={timestamp}"
            
            # Fallback: Check both profiles for any other roles (like admin)
            if hasattr(self, 'student_profile'):
                profile = self.student_profile
                if profile and profile.profile_picture:
                    timestamp = int(profile.updated_at.timestamp())
                    return f"{profile.profile_picture.url}?v={timestamp}"
            
            if hasattr(self, 'teacher_profile'):
                profile = self.teacher_profile
                if profile and profile.profile_picture:
                    timestamp = int(profile.updated_at.timestamp())
                    return f"{profile.profile_picture.url}?v={timestamp}"
                    
        except Exception:
            pass
        return None


class StudentProfile(models.Model):
    """Extended profile for students"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    bio = models.TextField(_('bio'), blank=True)
    profile_picture = models.ImageField(_('profile picture'), upload_to='profiles/students/', blank=True, null=True)
    date_of_birth = models.DateField(_('date of birth'), blank=True, null=True)
    
    # Preferences
    preferred_language = models.CharField(_('preferred language'), max_length=10, default='en')
    notification_enabled = models.BooleanField(_('notifications enabled'), default=True)
    
    # App Settings (for mobile app)
    notifications_enabled = models.BooleanField(_('notifications enabled'), default=True)
    email_notifications = models.BooleanField(_('email notifications'), default=True)
    push_notifications = models.BooleanField(_('push notifications'), default=True)
    auto_play_next = models.BooleanField(_('auto play next'), default=True)
    download_quality = models.CharField(
        _('download quality'),
        max_length=20,
        choices=(('low', 'Low'), ('medium', 'Medium'), ('high', 'High')),
        default='high'
    )
    playback_speed = models.DecimalField(
        _('playback speed'),
        max_digits=3,
        decimal_places=2,
        default=1.0,
        help_text="Audio playback speed (0.5 to 2.0)"
    )
    theme = models.CharField(
        _('theme'),
        max_length=10,
        choices=(('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')),
        default='light'
    )
    language = models.CharField(_('app language'), max_length=10, default='en')
    
    # Learning Goals
    weekly_goal_hours = models.IntegerField(_('weekly goal (hours)'), default=5, 
                                           help_text="Target learning hours per week")
    daily_goal_minutes = models.IntegerField(_('daily goal (minutes)'), default=30,
                                            help_text="Target learning minutes per day")
    
    # Stats
    total_courses_enrolled = models.IntegerField(_('total courses enrolled'), default=0)
    total_listening_hours = models.DecimalField(_('total listening hours'), max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('student profile')
        verbose_name_plural = _('student profiles')

    def __str__(self):
        return f"{self.user.email}'s profile"


class TeacherProfile(models.Model):
    """Extended profile for teachers"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    bio = models.TextField(_('bio'))
    profile_picture = models.ImageField(_('profile picture'), upload_to='profiles/teachers/', blank=True, null=True)
    expertise = models.CharField(_('expertise'), max_length=255, help_text="E.g., Mathematics, Science, Music")
    
    # Verification & Status
    is_verified = models.BooleanField(_('verified'), default=False, help_text="Admin verification status")
    verification_date = models.DateTimeField(_('verification date'), blank=True, null=True)
    
    # Social Links
    website = models.URLField(_('website'), blank=True)
    linkedin = models.URLField(_('LinkedIn'), blank=True)
    twitter = models.URLField(_('Twitter'), blank=True)
    
    # Stats
    total_courses = models.IntegerField(_('total courses'), default=0)
    total_students = models.IntegerField(_('total students'), default=0)
    average_rating = models.DecimalField(_('average rating'), max_digits=3, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('teacher profile')
        verbose_name_plural = _('teacher profiles')

    def __str__(self):
        return f"{self.user.email}'s profile"


class Address(models.Model):
    """Address model for users"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(_('address type'), max_length=10, choices=(
        ('billing', 'Billing'),
        ('shipping', 'Shipping'),
    ), default='billing')
    
    street_address = models.CharField(_('street address'), max_length=255)
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state'), max_length=100)
    postal_code = models.CharField(_('postal code'), max_length=20)
    country = models.CharField(_('country'), max_length=100, default='India')
    
    is_default = models.BooleanField(_('default address'), default=False)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('address')
        verbose_name_plural = _('addresses')
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.address_type}"

    def save(self, *args, **kwargs):
        """Ensure only one default address per user"""
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

