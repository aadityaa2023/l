from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class Banner(models.Model):
    """
    Promotional banners for the course selling platform
    Supports home page, course page, and special offer banners
    """
    
    BANNER_TYPE_CHOICES = (
        ('home', 'Home Page'),
        ('course', 'Course Page'),
        ('offer', 'Special Offer'),
    )
    
    # Basic Info
    title = models.CharField(_('title'), max_length=200, help_text=_('Banner title/headline'))
    description = models.TextField(_('description'), help_text=_('Banner description/message'))
    
    # Image
    image = models.ImageField(
        _('banner image'), 
        upload_to='banners/%Y/%m/', 
        help_text=_('Banner image (recommended: 1920x600px)')
    )
    
    # Call to Action
    button_text = models.CharField(
        _('button text'), 
        max_length=100, 
        blank=True, 
        help_text=_('Text for the CTA button (e.g., "Enroll Now", "Learn More")')
    )
    button_link = models.CharField(
        _('button link'), 
        max_length=500, 
        blank=True, 
        help_text=_('URL or path for the CTA button')
    )
    
    # Banner Type
    banner_type = models.CharField(
        _('banner type'), 
        max_length=20, 
        choices=BANNER_TYPE_CHOICES, 
        default='home',
        help_text=_('Where should this banner be displayed?')
    )
    
    # Display settings
    priority = models.PositiveIntegerField(
        _('priority'), 
        default=0, 
        help_text=_('Higher priority banners appear first (0-100)')
    )
    is_active = models.BooleanField(_('active'), default=True, help_text=_('Inactive banners are not displayed'))
    
    # Scheduling
    start_date = models.DateTimeField(_('start date'), default=timezone.now, help_text=_('Banner becomes active from this date'))
    end_date = models.DateTimeField(_('end date'), null=True, blank=True, help_text=_('Leave blank for no expiration'))
    
    # Metadata
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_banners',
        verbose_name=_('created by')
    )

    class Meta:
        verbose_name = _('banner')
        verbose_name_plural = _('banners')
        ordering = ['-priority', '-start_date']
        indexes = [
            models.Index(fields=['is_active', 'start_date', 'end_date']),
            models.Index(fields=['banner_type', 'priority']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_banner_type_display()})"
    
    def is_currently_active(self):
        """Check if banner is active and within scheduled time"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        
        # Check if started
        if self.start_date > now:
            return False
        
        # Check if expired
        if self.end_date and self.end_date < now:
            return False
        
        return True
    
    @classmethod
    def get_active_banners(cls, banner_type=None):
        """
        Get all currently active banners
        Args:
            banner_type (str, optional): Filter by banner type ('home', 'course', 'offer')
        Returns:
            QuerySet: Active banners sorted by priority
        """
        now = timezone.now()
        queryset = cls.objects.filter(
            is_active=True,
            start_date__lte=now,
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        )
        
        if banner_type:
            queryset = queryset.filter(banner_type=banner_type)
        
        return queryset.select_related('created_by')


class SiteSettings(models.Model):
    """Global site settings"""
    
    # Site Info
    site_name = models.CharField(_('site name'), max_length=100, default='Audio Learning Platform')
    site_tagline = models.CharField(_('tagline'), max_length=255, blank=True)
    site_description = models.TextField(_('description'), blank=True)
    
    # Contact
    contact_email = models.EmailField(_('contact email'), blank=True)
    contact_phone = models.CharField(_('contact phone'), max_length=20, blank=True)
    support_email = models.EmailField(_('support email'), blank=True)
    
    # Social Media
    facebook_url = models.URLField(_('Facebook URL'), blank=True)
    twitter_url = models.URLField(_('Twitter URL'), blank=True)
    instagram_url = models.URLField(_('Instagram URL'), blank=True)
    linkedin_url = models.URLField(_('LinkedIn URL'), blank=True)
    youtube_url = models.URLField(_('YouTube URL'), blank=True)
    
    # Features
    enable_registration = models.BooleanField(_('enable registration'), default=True)
    enable_payments = models.BooleanField(_('enable payments'), default=True)
    enable_reviews = models.BooleanField(_('enable reviews'), default=True)
    enable_notifications = models.BooleanField(_('enable notifications'), default=True)
    
    # Maintenance
    maintenance_mode = models.BooleanField(_('maintenance mode'), default=False)
    maintenance_message = models.TextField(_('maintenance message'), blank=True)
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    meta_keywords = models.CharField(_('meta keywords'), max_length=500, blank=True)
    
    # Analytics
    google_analytics_id = models.CharField(_('Google Analytics ID'), max_length=50, blank=True)
    facebook_pixel_id = models.CharField(_('Facebook Pixel ID'), max_length=50, blank=True)
    
    # Timestamps
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('site settings')
        verbose_name_plural = _('site settings')

    def __str__(self):
        return self.site_name
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


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
    is_published = models.BooleanField(_('published'), default=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['category', 'order']

    def __str__(self):
        return self.question


class ContactMessage(models.Model):
    """Contact form submissions"""
    
    STATUS_CHOICES = (
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    
    # Sender Info
    name = models.CharField(_('name'), max_length=100)
    email = models.EmailField(_('email'))
    phone = models.CharField(_('phone'), max_length=20, blank=True)
    
    # Message
    subject = models.CharField(_('subject'), max_length=255)
    message = models.TextField(_('message'))
    
    # Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='new')
    admin_notes = models.TextField(_('admin notes'), blank=True)
    
    # Assigned To
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_messages'
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    resolved_at = models.DateTimeField(_('resolved at'), null=True, blank=True)

    class Meta:
        verbose_name = _('contact message')
        verbose_name_plural = _('contact messages')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject}"


class Page(models.Model):
    """Static content pages"""
    
    title = models.CharField(_('title'), max_length=255)
    slug = models.SlugField(_('slug'), unique=True)
    content = models.TextField(_('content'))
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    
    # Settings
    is_published = models.BooleanField(_('published'), default=True)
    show_in_footer = models.BooleanField(_('show in footer'), default=False)
    order = models.PositiveIntegerField(_('order'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('page')
        verbose_name_plural = _('pages')
        ordering = ['order']

    def __str__(self):
        return self.title

