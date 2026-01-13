from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Category(models.Model):
    """Category for courses with hierarchical subcategory support"""
    
    name = models.CharField(_('name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True, blank=True)
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon class'), max_length=50, blank=True, help_text="CSS icon class (e.g., fas fa-code)")
    
    # Hierarchical structure
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='subcategories',
        help_text="Leave empty for main category, select a category to create subcategory"
    )
    
    # Display settings
    display_order = models.IntegerField(_('display order'), default=0, help_text="Lower numbers appear first")
    color = models.CharField(_('color code'), max_length=7, default='#667eea', help_text="Hex color code for UI")
    
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['display_order', 'name']
        unique_together = [['name', 'parent']]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            if self.parent:
                self.slug = f"{slugify(self.parent.name)}-{base_slug}"
            else:
                self.slug = base_slug
        super().save(*args, **kwargs)
    
    @property
    def full_name(self):
        """Get full category path"""
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    @property
    def is_subcategory(self):
        """Check if this is a subcategory"""
        return self.parent is not None
    
    @property
    def rgba_background(self):
        """Get rgba color for background with alpha 0.125"""
        hex_color = self.color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f'rgba({r}, {g}, {b}, 0.125)'
    
    @property
    def rgba_border(self):
        """Get rgba color for border with alpha 0.25"""
        hex_color = self.color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f'rgba({r}, {g}, {b}, 0.25)'
    
    @property
    def r(self):
        """Red component"""
        return int(self.color[1:3], 16)
    
    @property
    def g(self):
        """Green component"""
        return int(self.color[3:5], 16)
    
    @property
    def b(self):
        """Blue component"""
        return int(self.color[5:7], 16)
    
    def get_all_subcategories(self):
        """Get all subcategories recursively"""
        return self.subcategories.filter(is_active=True)


class Course(models.Model):
    """Main Course model"""
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    LEVEL_CHOICES = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    )
    
    # Basic Information
    title = models.CharField(_('title'), max_length=255)
    slug = models.SlugField(_('slug'), unique=True, blank=True)
    description = models.TextField(_('description'))
    short_description = models.CharField(_('short description'), max_length=500, blank=True)
    
    # Relations
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
        limit_choices_to={'role': 'teacher'},
        help_text="Assigned teacher for this course (assigned by platform admin)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_courses',
        help_text="Platform admin who created this course"
    )
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='courses')
    
    # Media
    thumbnail = models.ImageField(_('thumbnail'), upload_to='courses/thumbnails/', blank=True, null=True)
    intro_video_url = models.URLField(_('intro video URL'), blank=True)
    
    # Course Details
    level = models.CharField(_('level'), max_length=20, choices=LEVEL_CHOICES, default='beginner')
    language = models.CharField(_('language'), max_length=50, default='English')
    duration_hours = models.DecimalField(_('duration (hours)'), max_digits=5, decimal_places=2, default=0)
    
    # Pricing
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2, default=0)
    discount_price = models.DecimalField(_('discount price'), max_digits=10, decimal_places=2, null=True, blank=True)
    is_free = models.BooleanField(_('free course'), default=False)
    
    # Status & Settings
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(_('featured'), default=False)
    allow_download = models.BooleanField(_('allow download'), default=False, 
                                          help_text="Allow students to download audio files")
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    keywords = models.CharField(_('keywords'), max_length=255, blank=True)
    
    # Stats (auto-updated)
    total_lessons = models.IntegerField(_('total lessons'), default=0)
    total_enrollments = models.IntegerField(_('total enrollments'), default=0)
    average_rating = models.DecimalField(_('average rating'), max_digits=3, decimal_places=2, default=0)
    total_reviews = models.IntegerField(_('total reviews'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    published_at = models.DateTimeField(_('published at'), null=True, blank=True)

    class Meta:
        verbose_name = _('course')
        verbose_name_plural = _('courses')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['teacher', 'status']),
        ]

    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title) + '-' + str(uuid.uuid4())[:8]
        super().save(*args, **kwargs)
    
    @property
    def actual_price(self):
        """Return the actual price (discount if available, otherwise regular price)"""
        if self.is_free:
            return 0
        return self.discount_price if self.discount_price else self.price
    
    @property
    def is_on_sale(self):
        """Check if course is on sale"""
        return self.discount_price is not None and self.discount_price < self.price


class Module(models.Model):
    """Module/Section within a course"""
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    order = models.PositiveIntegerField(_('order'), default=0)
    
    is_published = models.BooleanField(_('published'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('module')
        verbose_name_plural = _('modules')
        ordering = ['course', 'order']
        unique_together = [['course', 'order']]

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lesson(models.Model):
    """Individual lesson/audio file within a module"""
    
    LESSON_TYPE_CHOICES = (
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('text', 'Text'),
        ('quiz', 'Quiz'),
    )
    
    # Relations
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    
    # Basic Info
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    lesson_type = models.CharField(_('lesson type'), max_length=10, choices=LESSON_TYPE_CHOICES, default='audio')
    order = models.PositiveIntegerField(_('order'), default=0)
    
    # Audio File (handled by audio app)
    audio_file = models.FileField(_('audio file'), upload_to='courses/lessons/', blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(_('duration (seconds)'), default=0)
    file_size = models.BigIntegerField(_('file size (bytes)'), default=0)
    
    # Content
    text_content = models.TextField(_('text content'), blank=True, help_text="For text-based lessons")
    
    # Settings
    is_free_preview = models.BooleanField(_('free preview'), default=False, 
                                           help_text="Allow non-enrolled students to access")
    is_published = models.BooleanField(_('published'), default=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('lesson')
        verbose_name_plural = _('lessons')
        ordering = ['module', 'order']
        unique_together = [['module', 'order']]
        indexes = [
            models.Index(fields=['course', 'is_published']),
            models.Index(fields=['module', 'order']),
        ]

    def __str__(self):
        return f"{self.module.title} - {self.title}"
    
    @property
    def get_audio_url(self):
        """Safely get the audio file URL"""
        if self.audio_file:
            try:
                return self.audio_file.url
            except (ValueError, AttributeError):
                # Handle cases where audio_file is a string path (legacy data)
                if isinstance(self.audio_file, str) and self.audio_file:
                    from django.conf import settings
                    return f"{settings.MEDIA_URL}{self.audio_file}"
        return None
    
    @property
    def duration_minutes(self):
        """Return duration in minutes"""
        if self.duration_seconds:
            return round(self.duration_seconds / 60, 1)
        return 0


class Enrollment(models.Model):
    """Student enrollment in a course"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )
    
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='enrollments',
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    
    # Enrollment Details
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='active')
    enrolled_at = models.DateTimeField(_('enrolled at'), auto_now_add=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    expires_at = models.DateTimeField(_('expires at'), null=True, blank=True)
    
    # Progress
    progress_percentage = models.DecimalField(_('progress percentage'), max_digits=5, decimal_places=2, default=0)
    total_listening_time = models.PositiveIntegerField(_('total listening time (seconds)'), default=0)
    lessons_completed = models.IntegerField(_('lessons completed'), default=0)
    
    # Payment (if applicable)
    payment_amount = models.DecimalField(_('payment amount'), max_digits=10, decimal_places=2, default=0)
    payment_reference = models.CharField(_('payment reference'), max_length=255, blank=True)
    
    # Timestamps
    last_accessed = models.DateTimeField(_('last accessed'), auto_now=True)

    class Meta:
        verbose_name = _('enrollment')
        verbose_name_plural = _('enrollments')
        unique_together = [['student', 'course']]
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
            models.Index(fields=['-enrolled_at']),
        ]

    def __str__(self):
        return f"{self.student.email} - {self.course.title}"

    def update_progress(self):
        """Recalculate and persist enrollment-level progress.

        - Aggregates related LessonProgress records to compute:
          * lessons_completed
          * progress_percentage (average of lesson completion percentages)
          * total_listening_time (sum of lesson total_time_spent)
          * last_accessed (most recent lesson access)
        - Marks enrollment as completed when progress reaches 100%.
        """
        from django.db.models import Avg, Sum, Max
        from decimal import Decimal

        # Total lessons for the course (prefer stored value, fallback to counting published lessons)
        total_lessons = 0
        try:
            if getattr(self.course, 'total_lessons', None):
                total_lessons = int(self.course.total_lessons)
            else:
                # Count published lessons related to this course
                from .models import Lesson as CourseLesson  # local import to avoid circulars
                total_lessons = CourseLesson.objects.filter(module__course=self.course, is_published=True).count()
        except Exception:
            total_lessons = 0

        # Aggregate lesson progress records
        lp_qs = self.lesson_progress.all()

        # Sum of completion percentages (decimal fields stored as Decimal)
        agg = lp_qs.aggregate(
            sum_completion=Sum('completion_percentage'),
            total_time=Sum('total_time_spent'),
            last_accessed=Max('last_accessed')
        )

        sum_completion = agg.get('sum_completion') or Decimal('0')
        # Count completed lessons safely
        lessons_completed = lp_qs.filter(is_completed=True).count()
        total_time = int(agg.get('total_time') or 0)
        last_accessed = agg.get('last_accessed')

        # If total_lessons is not available, try deriving from lesson_progress count
        if not total_lessons:
            total_lessons = lp_qs.count()

        # Compute progress percentage as average of lesson completion percentages
        progress_pct = Decimal('0')
        try:
            if total_lessons > 0:
                # sum_completion is in 0..100 per lesson; average it
                progress_pct = (Decimal(sum_completion) / Decimal(total_lessons))
                # Ensure within 0..100
                if progress_pct < 0:
                    progress_pct = Decimal('0')
                if progress_pct > 100:
                    progress_pct = Decimal('100')
        except Exception:
            progress_pct = Decimal('0')

        # Persist computed values
        self.lessons_completed = lessons_completed
        # progress_percentage field is DecimalField with 2 decimal places
        self.progress_percentage = round(progress_pct, 2)
        self.total_listening_time = total_time
        if last_accessed:
            self.last_accessed = last_accessed

        # Mark completed if progress is 100
        if self.progress_percentage >= Decimal('100') and self.status != 'completed':
            self.status = 'completed'
            from django.utils import timezone
            self.completed_at = self.completed_at or timezone.now()

        # Save without updating timestamps beyond last_accessed
        self.save()


class LessonProgress(models.Model):
    """Track individual lesson progress for students"""
    
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress_records')
    
    # Progress
    is_completed = models.BooleanField(_('completed'), default=False)
    last_position_seconds = models.PositiveIntegerField(_('last position (seconds)'), default=0)
    total_time_spent = models.PositiveIntegerField(_('total time spent (seconds)'), default=0)
    completion_percentage = models.DecimalField(_('completion percentage'), max_digits=5, decimal_places=2, default=0)
    
    # Timestamps
    first_accessed = models.DateTimeField(_('first accessed'), auto_now_add=True)
    last_accessed = models.DateTimeField(_('last accessed'), auto_now=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)

    class Meta:
        verbose_name = _('lesson progress')
        verbose_name_plural = _('lesson progresses')
        unique_together = [['enrollment', 'lesson']]
        ordering = ['-last_accessed']
        indexes = [
            models.Index(fields=['enrollment', 'is_completed']),
            models.Index(fields=['lesson', '-last_accessed']),
        ]

    def __str__(self):
        return f"{self.enrollment.student.email} - {self.lesson.title}"


class Note(models.Model):
    """Student notes for lessons"""
    
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='notes')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='notes')
    
    content = models.TextField(_('content'))
    timestamp_seconds = models.PositiveIntegerField(_('timestamp (seconds)'), default=0, 
                                                     help_text="Position in audio where note was taken")
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('note')
        verbose_name_plural = _('notes')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['enrollment', 'lesson']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"Note by {self.enrollment.student.email} on {self.lesson.title}"


class Review(models.Model):
    """Course reviews by students"""
    
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='review')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    
    rating = models.PositiveSmallIntegerField(_('rating'), validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(_('title'), max_length=255, blank=True)
    comment = models.TextField(_('comment'), blank=True)
    
    is_approved = models.BooleanField(_('approved'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('review')
        verbose_name_plural = _('reviews')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course', 'is_approved']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.student.email} - {self.course.title} ({self.rating}★)"


# ---------------------------------------------------------------------------
# Signals: keep enrollment aggregates in sync when lesson progress changes
# ---------------------------------------------------------------------------
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=LessonProgress)
def _on_lesson_progress_save(sender, instance: LessonProgress, **kwargs):
    try:
        if instance.enrollment:
            instance.enrollment.update_progress()
    except Exception:
        # Avoid raising during signal handling
        pass


@receiver(post_delete, sender=LessonProgress)
def _on_lesson_progress_delete(sender, instance: LessonProgress, **kwargs):
    try:
        if instance.enrollment:
            instance.enrollment.update_progress()
    except Exception:
        pass


class LessonMedia(models.Model):
    """Multiple media files (audio/video) for a single lesson"""
    
    MEDIA_TYPE_CHOICES = (
        ('audio', 'Audio'),
        ('video', 'Video'),
    )
    
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='media_files')
    
    # Media file
    media_file = models.FileField(_('media file'), upload_to='courses/lessons/media/')
    media_type = models.CharField(_('media type'), max_length=10, choices=MEDIA_TYPE_CHOICES)
    
    # File details
    title = models.CharField(_('title'), max_length=255, blank=True, help_text="Optional title for this media file")
    duration_seconds = models.PositiveIntegerField(_('duration (seconds)'), default=0)
    file_size = models.BigIntegerField(_('file size (bytes)'), default=0)
    order = models.PositiveIntegerField(_('order'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('lesson media')
        verbose_name_plural = _('lesson media')
        ordering = ['lesson', 'order']
        indexes = [
            models.Index(fields=['lesson', 'order']),
        ]
    
    def __str__(self):
        return f"{self.lesson.title} - {self.get_media_type_display()} {self.order + 1}"
    
    @property
    def get_media_url(self):
        """Safely get the media file URL"""
        if self.media_file:
            try:
                return self.media_file.url
            except (ValueError, AttributeError):
                if isinstance(self.media_file, str) and self.media_file:
                    from django.conf import settings
                    return f"{settings.MEDIA_URL}{self.media_file}"
        return None
    
    @property
    def duration_minutes(self):
        """Return duration in minutes"""
        if self.duration_seconds:
            return round(self.duration_seconds / 60, 1)
        return 0


class Announcement(models.Model):
    """Teacher announcements for enrolled students"""
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='announcements')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='announcements')
    
    title = models.CharField(_('title'), max_length=255)
    message = models.TextField(_('message'))
    
    is_published = models.BooleanField(_('published'), default=True)
    send_email = models.BooleanField(_('send email'), default=False, 
                                      help_text="Send email notification to enrolled students")
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('announcement')
        verbose_name_plural = _('announcements')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Certificate(models.Model):
    """Course completion certificates"""
    
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='certificates')
    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='certificate',
        null=True,
        blank=True
    )
    
    certificate_number = models.CharField(_('certificate number'), max_length=50, unique=True)
    verification_code = models.CharField(_('verification code'), max_length=50, unique=True)
    certificate_file = models.FileField(
        _('certificate file'),
        upload_to='certificates/',
        null=True,
        blank=True
    )
    
    issued_date = models.DateTimeField(_('issued date'), auto_now_add=True)
    expiry_date = models.DateTimeField(_('expiry date'), null=True, blank=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('certificate')
        verbose_name_plural = _('certificates')
        ordering = ['-issued_date']
        indexes = [
            models.Index(fields=['student', '-issued_date']),
            models.Index(fields=['certificate_number']),
            models.Index(fields=['verification_code']),
        ]

    def __str__(self):
        return f"{self.student.email} - {self.course.title} ({self.certificate_number})"
    
    def save(self, *args, **kwargs):
        if not self.certificate_number:
            import uuid
            self.certificate_number = f"LEQ-{uuid.uuid4().hex[:12].upper()}"
        if not self.verification_code:
            import uuid
            self.verification_code = uuid.uuid4().hex[:16].upper()
        super().save(*args, **kwargs)


class Download(models.Model):
    """Track offline lesson downloads"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='downloads'
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='downloads')
    
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    file_size = models.BigIntegerField(_('file size (bytes)'), default=0)
    downloaded_at = models.DateTimeField(_('downloaded at'), null=True, blank=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('download')
        verbose_name_plural = _('downloads')
        ordering = ['-created_at']
        unique_together = [['user', 'lesson']]
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.lesson.title} ({self.status})"

