from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid


class AdminRole(models.Model):
    """Store admin role assignments for granular permissions"""
    
    ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),
        ('content_moderator', 'Content Moderator'),
        ('finance_admin', 'Finance Admin'),
        ('user_support', 'User Support'),
        ('analytics_viewer', 'Analytics Viewer'),
        ('platform_admin', 'Platform Admin'),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_role_assignment'
    )
    role = models.CharField(
        _('admin role'),
        max_length=30,
        choices=ROLE_CHOICES,
        default='platform_admin'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_roles'
    )
    assigned_at = models.DateTimeField(_('assigned at'), auto_now_add=True)
    notes = models.TextField(_('notes'), blank=True)
    
    class Meta:
        verbose_name = _('admin role')
        verbose_name_plural = _('admin roles')
    
    def __str__(self):
        return f"{self.user.email} - {self.get_role_display()}"


class AdminLog(models.Model):
    """Track all admin activities for audit purposes"""
    
    ACTION_CHOICES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('suspend', 'Suspend'),
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('refund', 'Refund'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='admin_logs')
    action = models.CharField(_('action'), max_length=20, choices=ACTION_CHOICES)
    content_type = models.CharField(_('content type'), max_length=100)  # e.g., 'User', 'Course', 'Payment'
    object_id = models.CharField(_('object ID'), max_length=255)
    object_repr = models.CharField(_('object representation'), max_length=255)
    
    old_values = models.JSONField(_('old values'), default=dict, blank=True)
    new_values = models.JSONField(_('new values'), default=dict, blank=True)
    
    reason = models.TextField(_('reason'), blank=True)
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.CharField(_('user agent'), max_length=500, blank=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('admin log')
        verbose_name_plural = _('admin logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.admin.email} - {self.action} {self.content_type} ({self.created_at})"


class CourseApproval(models.Model):
    """Track course approval workflow"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('revision_requested', 'Revision Requested'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.OneToOneField('courses.Course', on_delete=models.CASCADE, related_name='approval')
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    
    submitted_at = models.DateTimeField(_('submitted at'), auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='course_approvals')
    reviewed_at = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    
    review_comments = models.TextField(_('review comments'), blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('course approval')
        verbose_name_plural = _('course approvals')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.course.title} - {self.status}"


class DashboardStat(models.Model):
    """Store daily dashboard statistics for performance"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(_('date'), unique=True)
    
    total_users = models.IntegerField(_('total users'), default=0)
    total_teachers = models.IntegerField(_('total teachers'), default=0)
    total_students = models.IntegerField(_('total students'), default=0)
    
    total_courses = models.IntegerField(_('total courses'), default=0)
    published_courses = models.IntegerField(_('published courses'), default=0)
    pending_approval_courses = models.IntegerField(_('pending approval'), default=0)
    
    total_enrollments = models.IntegerField(_('total enrollments'), default=0)
    total_revenue = models.DecimalField(_('total revenue'), max_digits=15, decimal_places=2, default=0)
    completed_transactions = models.IntegerField(_('completed transactions'), default=0)
    failed_transactions = models.IntegerField(_('failed transactions'), default=0)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('dashboard stat')
        verbose_name_plural = _('dashboard stats')
        ordering = ['-date']

    def __str__(self):
        return f"Stats for {self.date}"


class PlatformSetting(models.Model):
    """Global platform settings managed by admin"""
    
    SETTING_TYPE_CHOICES = (
        ('string', 'String'),
        ('integer', 'Integer'),
        ('decimal', 'Decimal'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
    )
    
    key = models.CharField(_('key'), max_length=100, unique=True)
    value = models.TextField(_('value'))
    setting_type = models.CharField(_('type'), max_length=20, choices=SETTING_TYPE_CHOICES, default='string')
    description = models.TextField(_('description'), blank=True)
    is_public = models.BooleanField(_('public'), default=False, help_text="Is this setting visible to public?")
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('platform setting')
        verbose_name_plural = _('platform settings')

    def __str__(self):
        return self.key


class LoginHistory(models.Model):
    """Track user login attempts and sessions"""
    
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('blocked', 'Blocked'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='login_history',
        null=True,
        blank=True
    )
    email = models.EmailField(_('email'))
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES)
    
    # Device & Location Info
    ip_address = models.GenericIPAddressField(_('IP address'))
    user_agent = models.CharField(_('user agent'), max_length=500)
    device_type = models.CharField(_('device type'), max_length=50, blank=True)
    browser = models.CharField(_('browser'), max_length=100, blank=True)
    os = models.CharField(_('operating system'), max_length=100, blank=True)
    country = models.CharField(_('country'), max_length=100, blank=True)
    city = models.CharField(_('city'), max_length=100, blank=True)
    
    # Session Info
    session_key = models.CharField(_('session key'), max_length=255, blank=True)
    
    # Failure Details
    failure_reason = models.CharField(_('failure reason'), max_length=255, blank=True)
    
    # Timestamps
    attempted_at = models.DateTimeField(_('attempted at'), auto_now_add=True)
    logout_at = models.DateTimeField(_('logout at'), null=True, blank=True)

    class Meta:
        verbose_name = _('login history')
        verbose_name_plural = _('login histories')
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['user', '-attempted_at']),
            models.Index(fields=['email', '-attempted_at']),
            models.Index(fields=['ip_address', '-attempted_at']),
        ]

    def __str__(self):
        return f"{self.email} - {self.status} ({self.attempted_at})"


class CMSPage(models.Model):
    """Content Management System - Static pages"""
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )
    
    title = models.CharField(_('title'), max_length=255)
    slug = models.SlugField(_('slug'), unique=True)
    content = models.TextField(_('content'))
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    meta_keywords = models.CharField(_('meta keywords'), max_length=255, blank=True)
    
    # Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    is_in_menu = models.BooleanField(_('show in menu'), default=True)
    menu_order = models.PositiveIntegerField(_('menu order'), default=0)
    
    # Timestamps
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_pages'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('CMS page')
        verbose_name_plural = _('CMS pages')
        ordering = ['menu_order', 'title']

    def __str__(self):
        return self.title


class FAQ(models.Model):
    """Frequently Asked Questions"""
    
    CATEGORY_CHOICES = (
        ('general', 'General'),
        ('courses', 'Courses'),
        ('payments', 'Payments'),
        ('technical', 'Technical'),
        ('account', 'Account'),
    )
    
    question = models.CharField(_('question'), max_length=500)
    answer = models.TextField(_('answer'))
    category = models.CharField(_('category'), max_length=20, choices=CATEGORY_CHOICES, default='general')
    
    order = models.PositiveIntegerField(_('order'), default=0)
    is_active = models.BooleanField(_('active'), default=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['category', 'order']

    def __str__(self):
        return self.question


class Announcement(models.Model):
    """Platform-wide announcements and banners"""
    
    TYPE_CHOICES = (
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('danger', 'Danger'),
    )
    
    DISPLAY_LOCATION_CHOICES = (
        ('banner', 'Banner (top of page)'),
        ('popup', 'Popup'),
        ('dashboard', 'Dashboard only'),
    )
    
    title = models.CharField(_('title'), max_length=255)
    message = models.TextField(_('message'))
    announcement_type = models.CharField(_('type'), max_length=20, choices=TYPE_CHOICES, default='info')
    display_location = models.CharField(_('display location'), max_length=20, choices=DISPLAY_LOCATION_CHOICES, default='banner')
    
    # Targeting
    target_all_users = models.BooleanField(_('all users'), default=True)
    target_students = models.BooleanField(_('students'), default=False)
    target_teachers = models.BooleanField(_('teachers'), default=False)
    
    # Schedule
    is_active = models.BooleanField(_('active'), default=True)
    start_date = models.DateTimeField(_('start date'))
    end_date = models.DateTimeField(_('end date'), null=True, blank=True)
    
    # Timestamps
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements_created'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('announcement')
        verbose_name_plural = _('announcements')
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class InstructorPayout(models.Model):
    """Track instructor earnings and payouts"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('requested', 'Requested'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('on_hold', 'On Hold'),
    )
    
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payouts',
        limit_choices_to={'role': 'teacher'}
    )
    
    # Amount Details
    gross_amount = models.DecimalField(_('gross amount'), max_digits=10, decimal_places=2,
                                        help_text="Total earnings before platform commission")
    platform_commission = models.DecimalField(_('platform commission'), max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(_('net amount'), max_digits=10, decimal_places=2,
                                      help_text="Amount payable to instructor")
    
    # Commission Rate (stored for historical reference)
    commission_rate = models.DecimalField(_('commission rate'), max_digits=5, decimal_places=2,
                                           help_text="Platform commission percentage")
    
    # Payout Details
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(_('payment method'), max_length=50, blank=True,
                                       help_text="Bank transfer, UPI, etc.")
    transaction_reference = models.CharField(_('transaction reference'), max_length=255, blank=True)
    
    # Bank Details (for reference)
    bank_details = models.JSONField(_('bank details'), default=dict, blank=True)
    
    # Period
    period_start = models.DateField(_('period start'))
    period_end = models.DateField(_('period end'))
    
    # Notes
    instructor_notes = models.TextField(_('instructor notes'), blank=True)
    admin_notes = models.TextField(_('admin notes'), blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    
    # Processing
    requested_at = models.DateTimeField(_('requested at'), null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payouts'
    )
    processed_at = models.DateTimeField(_('processed at'), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('instructor payout')
        verbose_name_plural = _('instructor payouts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['instructor', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.instructor.email} - ₹{self.net_amount} ({self.status})"


class ReferralProgram(models.Model):
    """Referral and affiliate program"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_program'
    )
    
    # Referral Code
    referral_code = models.CharField(_('referral code'), max_length=50, unique=True)
    
    # Commission Settings
    commission_type = models.CharField(_('commission type'), max_length=20,
                                        choices=(('percentage', 'Percentage'), ('fixed', 'Fixed')),
                                        default='percentage')
    commission_value = models.DecimalField(_('commission value'), max_digits=10, decimal_places=2, default=10)
    
    # Stats
    total_referrals = models.PositiveIntegerField(_('total referrals'), default=0)
    successful_conversions = models.PositiveIntegerField(_('successful conversions'), default=0)
    total_earnings = models.DecimalField(_('total earnings'), max_digits=10, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('referral program')
        verbose_name_plural = _('referral programs')

    def __str__(self):
        return f"{self.user.email} - {self.referral_code}"


class Referral(models.Model):
    """Track individual referrals"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('signed_up', 'Signed Up'),
        ('converted', 'Converted'),
        ('expired', 'Expired'),
    )
    
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_made'
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referred_by',
        null=True,
        blank=True
    )
    
    # Referral Details
    referral_code = models.CharField(_('referral code'), max_length=50)
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Conversion Details
    converted_payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_conversion'
    )
    commission_earned = models.DecimalField(_('commission earned'), max_digits=10, decimal_places=2, default=0)
    
    # Timestamps
    referred_at = models.DateTimeField(_('referred at'), auto_now_add=True)
    signed_up_at = models.DateTimeField(_('signed up at'), null=True, blank=True)
    converted_at = models.DateTimeField(_('converted at'), null=True, blank=True)

    class Meta:
        verbose_name = _('referral')
        verbose_name_plural = _('referrals')
        ordering = ['-referred_at']
        indexes = [
            models.Index(fields=['referrer', '-referred_at']),
            models.Index(fields=['referral_code']),
        ]

    def __str__(self):
        return f"{self.referrer.email} referred {self.referred_user.email if self.referred_user else 'Unknown'}"


class VideoSettings(models.Model):
    """Video streaming and DRM settings"""
    
    # DRM Settings
    enable_drm = models.BooleanField(_('enable DRM'), default=False)
    enable_watermark = models.BooleanField(_('enable watermark'), default=True)
    watermark_text = models.CharField(_('watermark text'), max_length=100, default='{{user_email}}',
                                       help_text="Use {{user_email}} or {{user_id}} as placeholders")
    
    # Download Settings
    allow_download_default = models.BooleanField(_('allow download by default'), default=False)
    
    # Streaming Settings
    max_video_quality = models.CharField(_('max video quality'), max_length=20,
                                          choices=(('360p', '360p'), ('480p', '480p'), ('720p', '720p'), ('1080p', '1080p')),
                                          default='720p')
    enable_adaptive_streaming = models.BooleanField(_('enable adaptive streaming'), default=True)
    
    # Security
    max_concurrent_devices = models.PositiveIntegerField(_('max concurrent devices'), default=2)
    session_timeout_minutes = models.PositiveIntegerField(_('session timeout (minutes)'), default=30)
    
    # Piracy Detection
    enable_piracy_alerts = models.BooleanField(_('enable piracy alerts'), default=True)
    suspicious_download_threshold = models.PositiveIntegerField(_('suspicious download threshold'), default=5,
                                                                  help_text="Downloads per hour to trigger alert")
    
    # Timestamps
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('video settings')
        verbose_name_plural = _('video settings')

    def __str__(self):
        return "Video Settings"


class CourseAssignment(models.Model):
    """Track course assignments from platform admin to teachers"""
    
    STATUS_CHOICES = (
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('revoked', 'Revoked'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_assignments',
        limit_choices_to={'role': 'teacher'}
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_courses',
        limit_choices_to={'role': 'admin'}
    )
    
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='assigned')
    
    # Permissions
    can_edit_content = models.BooleanField(_('can edit content'), default=True, 
                                            help_text="Allow teacher to add and edit lessons and modules")
    can_delete_content = models.BooleanField(_('can delete content'), default=False,
                                              help_text="Allow teacher to delete lessons and modules")
    can_edit_details = models.BooleanField(_('can edit course details'), default=False,
                                            help_text="Allow teacher to edit course title, description, pricing")
    can_publish = models.BooleanField(_('can publish'), default=False,
                                       help_text="Allow teacher to publish/unpublish course")
    
    # Commission Settings (per teacher per course)
    commission_percentage = models.DecimalField(
        _('commission percentage'), 
        max_digits=5, 
        decimal_places=2, 
        null=True,
        blank=True,
        default=None,
        help_text="Platform commission percentage for this teacher on this course (leave empty to use platform default)"
    )
    
    # Assigned Coupons (Teacher-specific coupons)
    assigned_coupons = models.ManyToManyField(
        'payments.Coupon',
        blank=True,
        related_name='teacher_assignments',
        help_text="Coupons assigned to this teacher for this course"
    )
    
    # Notes
    assignment_notes = models.TextField(_('assignment notes'), blank=True,
                                         help_text="Admin notes about this assignment")
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    
    # Timestamps
    assigned_at = models.DateTimeField(_('assigned at'), auto_now_add=True)
    accepted_at = models.DateTimeField(_('accepted at'), null=True, blank=True)
    rejected_at = models.DateTimeField(_('rejected at'), null=True, blank=True)
    revoked_at = models.DateTimeField(_('revoked at'), null=True, blank=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('course assignment')
        verbose_name_plural = _('course assignments')
        ordering = ['-assigned_at']
        unique_together = [['course', 'teacher']]
        indexes = [
            models.Index(fields=['teacher', 'status']),
            models.Index(fields=['course', 'status']),
            models.Index(fields=['-assigned_at']),
        ]

    def __str__(self):
        return f"{self.course.title} → {self.teacher.email} ({self.status})"


# ---------------------------------------------------------------------------
# Signals: when a CourseAssignment is created/updated to 'assigned',
# automatically set the Course.teacher and notify the teacher.
# ---------------------------------------------------------------------------
from django.db.models.signals import post_save
from django.dispatch import receiver

try:
    # import here to avoid circular import problems at module import time
    from apps.notifications.models import Notification
except Exception:
    Notification = None


@receiver(post_save, sender=CourseAssignment)
def _on_course_assignment_save(sender, instance: CourseAssignment, created, **kwargs):
    try:
        # When assignment status is 'assigned', make the course's teacher match
        if instance.status == 'assigned' and instance.course:
            course = instance.course
            if course.teacher != instance.teacher:
                course.teacher = instance.teacher
                course.save()

            # Create a notification for the teacher if notifications are available
            if Notification is not None:
                try:
                    Notification.objects.create(
                        user=instance.teacher,
                        notification_type='course_assignment',
                        title=f"New course assigned: {course.title}",
                        message=f"You have been assigned the course '{course.title}' by the platform.",
                        course=course,
                        send_email=False,
                    )
                except Exception:
                    # Don't let notification failures break assignment flow
                    pass
    except Exception:
        # Avoid raising during signal handling
        pass


class TeacherCommission(models.Model):
    """Track teacher commission earnings and payout balances"""
    
    teacher = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commission_balance',
        limit_choices_to={'role': 'teacher'}
    )
    
    # Total earnings from all course sales
    total_earned = models.DecimalField(
        _('total earned'), 
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Total commission earned from all course purchases"
    )
    
    # Total amount already paid out
    total_paid = models.DecimalField(
        _('total paid'), 
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Total amount already paid to teacher"
    )
    
    # Remaining payable balance (calculated field)
    @property
    def remaining_balance(self):
        """Calculate remaining payable commission"""
        return self.total_earned - self.total_paid
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    last_payout_at = models.DateTimeField(_('last payout at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('teacher commission')
        verbose_name_plural = _('teacher commissions')
        ordering = ['-total_earned']
        indexes = [
            models.Index(fields=['teacher']),
            models.Index(fields=['-total_earned']),
        ]
    
    def __str__(self):
        return f"{self.teacher.email} - Earned: ₹{self.total_earned}, Paid: ₹{self.total_paid}, Remaining: ₹{self.remaining_balance}"


class PayoutTransaction(models.Model):
    """Record each payout transaction to teachers"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payout_transactions',
        limit_choices_to={'role': 'teacher'}
    )
    
    # Amount details
    amount = models.DecimalField(
        _('payout amount'), 
        max_digits=10, 
        decimal_places=2,
        help_text="Amount paid out in this transaction"
    )
    
    # Transaction details
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(
        _('payment method'), 
        max_length=100, 
        blank=True,
        help_text="e.g., Bank Transfer, UPI, etc."
    )
    transaction_reference = models.CharField(
        _('transaction reference'), 
        max_length=255, 
        blank=True,
        help_text="Bank transaction ID or reference number"
    )
    
    # Processing details
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='processed_payout_transactions',
        limit_choices_to={'role': 'admin'}
    )
    
    # Notes
    admin_notes = models.TextField(_('admin notes'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    processed_at = models.DateTimeField(_('processed at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('payout transaction')
        verbose_name_plural = _('payout transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Payout to {self.teacher.email} - ₹{self.amount} ({self.status})"


# Signal to update TeacherCommission when Payment is completed
# DISABLED: This signal was causing double-counting of teacher commissions.
# Commission updates are now handled exclusively by CommissionCalculator.record_commission_on_payment()
# which includes proper idempotency checks to prevent duplicate recording.
#
# @receiver(post_save, sender='payments.Payment')
# def update_teacher_commission_on_payment(sender, instance, created, **kwargs):
#     """
#     Update teacher commission balance when a payment is completed
#     
#     This signal:
#     1. Calculates and deducts Razorpay fees (2% + 18% GST) from gross payment
#     2. Splits the net amount between platform admin and teacher based on commission percentage
#     3. Updates teacher's total_earned with their share of the net amount
#     """
#     if instance.status == 'completed' and instance.course:
#         from apps.payments.commission_calculator import CommissionCalculator
#         
#         # First, ensure Razorpay fees are calculated and stored
#         if not instance.net_amount or instance.net_amount == 0:
#             instance.calculate_and_set_fees()
#             instance.save(update_fields=['razorpay_fee', 'razorpay_gst', 'net_amount'])
#         
#         # Calculate teacher commission on net amount (after Razorpay fees)
#         commission_data = CommissionCalculator.calculate_commission(instance)
#         teacher_revenue = commission_data.get('teacher_revenue', 0)
#         
#         # Get the teacher from course assignment
#         teacher = None
#         assignment = CommissionCalculator.get_teacher_assignment(instance.course)
#         if assignment:
#             teacher = assignment.teacher
#         elif instance.course.teacher:
#             teacher = instance.course.teacher
#         
#         if teacher and teacher_revenue > 0:
#             # Get or create TeacherCommission record
#             commission, created = TeacherCommission.objects.get_or_create(
#                 teacher=teacher
#             )
#             
#             # Add to total earned (teacher's share of net amount)
#             commission.total_earned += teacher_revenue
#             commission.save()


class FreeUser(models.Model):
    """Users assigned free access to all paid courses by platform admin"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='free_user_profile',
        limit_choices_to={'role': 'student'}
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_free_users',
        limit_choices_to={'role': 'admin'}
    )
    
    # Status and details
    is_active = models.BooleanField(_('active'), default=True, help_text="If inactive, user loses free access")
    reason = models.TextField(_('reason for free access'), blank=True, help_text="Admin notes about why this user has free access")
    
    # Restrictions (optional)
    expires_at = models.DateTimeField(_('expires at'), null=True, blank=True, help_text="Leave empty for unlimited access")
    max_courses = models.PositiveIntegerField(_('max courses'), null=True, blank=True, help_text="Leave empty for unlimited courses")
    
    # Timestamps
    assigned_at = models.DateTimeField(_('assigned at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('free user')
        verbose_name_plural = _('free users')
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['is_active', '-assigned_at']),
        ]
    
    def __str__(self):
        return f"Free User: {self.user.email} ({'Active' if self.is_active else 'Inactive'})"
    
    def is_expired(self):
        """Check if free access has expired"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False
    
    def has_access(self):
        """Check if user currently has free access"""
        return self.is_active and not self.is_expired()
    
    def get_enrolled_courses_count(self):
        """Get count of courses user is enrolled in"""
        return self.user.enrollments.filter(status='active').count()










class FooterSettings(models.Model):
    """Footer content and social media links - Singleton model"""
    
    # Company info
    company_name = models.CharField(_('company name'), max_length=200, default='LeQ')
    company_description = models.TextField(_('company description'), blank=True, help_text="Short description in footer")
    
    # Contact info
    contact_email = models.EmailField(_('contact email'), blank=True)
    contact_phone = models.CharField(_('contact phone'), max_length=20, blank=True)
    contact_address = models.TextField(_('contact address'), blank=True)
    
    # Social media links
    facebook_url = models.URLField(_('Facebook URL'), blank=True)
    twitter_url = models.URLField(_('Twitter URL'), blank=True)
    instagram_url = models.URLField(_('Instagram URL'), blank=True)
    linkedin_url = models.URLField(_('LinkedIn URL'), blank=True)
    youtube_url = models.URLField(_('YouTube URL'), blank=True)
    github_url = models.URLField(_('GitHub URL'), blank=True)
    
    # Footer text
    copyright_text = models.CharField(
        _('copyright text'), 
        max_length=200, 
        default='© 2024 LeQ. All rights reserved.',
        help_text="Copyright notice in footer"
    )
    
    # Additional links
    privacy_policy_url = models.URLField(_('Privacy Policy URL'), blank=True)
    terms_of_service_url = models.URLField(_('Terms of Service URL'), blank=True)
    
    # Newsletter
    show_newsletter_signup = models.BooleanField(_('show newsletter signup'), default=True)
    newsletter_heading = models.CharField(_('newsletter heading'), max_length=200, default='Subscribe to our Newsletter')
    newsletter_description = models.TextField(_('newsletter description'), blank=True, default='Get the latest updates and news.')
    
    # Timestamps
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='footer_updates'
    )
    
    class Meta:
        verbose_name = _('footer settings')
        verbose_name_plural = _('footer settings')
    
    def __str__(self):
        return "Footer Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class PageContent(models.Model):
    """Manage content for template-based pages like About Us, Contact Us, etc."""
    
    PAGE_TYPE_CHOICES = (
        ('about_us', 'About Us'),
        ('contact_us', 'Contact Us'),
        ('privacy_policy', 'Privacy Policy'),
        ('terms_of_service', 'Terms of Service'),
        ('faq', 'FAQ'),
        ('custom', 'Custom Page'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )
    
    # Page identification
    page_type = models.CharField(_('page type'), max_length=50, choices=PAGE_TYPE_CHOICES, unique=True)
    title = models.CharField(_('page title'), max_length=200)
    slug = models.SlugField(_('slug'), unique=True, help_text="URL-friendly version of the title")
    
    # Content sections
    hero_title = models.CharField(_('hero title'), max_length=200, blank=True, help_text="Main heading at top of page")
    hero_subtitle = models.TextField(_('hero subtitle'), blank=True, help_text="Subtitle or tagline")
    hero_image = models.ImageField(_('hero image'), upload_to='page_content/', blank=True)
    
    # Main content
    content = models.TextField(_('main content'), help_text="Main page content (HTML supported)")
    
    # Additional sections (JSON for flexibility)
    additional_sections = models.JSONField(
        _('additional sections'), 
        default=dict, 
        blank=True,
        help_text="Additional content sections in JSON format"
    )
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=200, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    meta_keywords = models.CharField(_('meta keywords'), max_length=255, blank=True)
    
    # Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='published')
    show_in_footer = models.BooleanField(_('show in footer'), default=True, help_text="Display link in footer")
    show_in_header = models.BooleanField(_('show in header'), default=False, help_text="Display link in header menu")
    
    # Display order
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_page_contents'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_page_contents'
    )
    
    class Meta:
        verbose_name = _('page content')
        verbose_name_plural = _('page contents')
        ordering = ['display_order', 'title']
    
    def __str__(self):
        return f"{self.get_page_type_display()} - {self.title}"
