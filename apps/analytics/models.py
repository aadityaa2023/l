from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class ListeningSession(models.Model):
    """Track individual listening sessions"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listening_sessions')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='listening_sessions')
    enrollment = models.ForeignKey('courses.Enrollment', on_delete=models.CASCADE, related_name='listening_sessions')
    
    # Session Details
    session_id = models.CharField(_('session ID'), max_length=100, unique=True)
    started_at = models.DateTimeField(_('started at'), auto_now_add=True)
    ended_at = models.DateTimeField(_('ended at'), null=True, blank=True)
    
    # Listening Info
    duration_seconds = models.PositiveIntegerField(_('duration (seconds)'), default=0)
    start_position = models.PositiveIntegerField(_('start position (seconds)'), default=0)
    end_position = models.PositiveIntegerField(_('end position (seconds)'), default=0)
    completed = models.BooleanField(_('completed'), default=False)
    
    # Device & Location
    device_type = models.CharField(_('device type'), max_length=50, blank=True)
    browser = models.CharField(_('browser'), max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)

    class Meta:
        verbose_name = _('listening session')
        verbose_name_plural = _('listening sessions')
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', '-started_at']),
            models.Index(fields=['lesson', '-started_at']),
            models.Index(fields=['-started_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.lesson.title} ({self.started_at})"


class DailyAnalytics(models.Model):
    """Aggregated daily analytics"""
    
    date = models.DateField(_('date'), unique=True)
    
    # User Metrics
    total_active_users = models.IntegerField(_('total active users'), default=0)
    new_users = models.IntegerField(_('new users'), default=0)
    total_students = models.IntegerField(_('total students'), default=0)
    total_teachers = models.IntegerField(_('total teachers'), default=0)
    
    # Course Metrics
    total_courses = models.IntegerField(_('total courses'), default=0)
    new_courses = models.IntegerField(_('new courses'), default=0)
    total_lessons = models.IntegerField(_('total lessons'), default=0)
    
    # Enrollment Metrics
    total_enrollments = models.IntegerField(_('total enrollments'), default=0)
    new_enrollments = models.IntegerField(_('new enrollments'), default=0)
    active_enrollments = models.IntegerField(_('active enrollments'), default=0)
    
    # Listening Metrics
    total_listening_hours = models.DecimalField(_('total listening hours'), max_digits=10, decimal_places=2, default=0)
    total_sessions = models.IntegerField(_('total sessions'), default=0)
    avg_session_duration = models.DecimalField(_('avg session duration (min)'), max_digits=10, decimal_places=2, default=0)
    
    # Revenue Metrics
    total_revenue = models.DecimalField(_('total revenue'), max_digits=12, decimal_places=2, default=0)
    total_payments = models.IntegerField(_('total payments'), default=0)
    successful_payments = models.IntegerField(_('successful payments'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('daily analytics')
        verbose_name_plural = _('daily analytics')
        ordering = ['-date']

    def __str__(self):
        return f"Analytics for {self.date}"


class CourseAnalytics(models.Model):
    """Analytics per course"""
    
    course = models.OneToOneField('courses.Course', on_delete=models.CASCADE, related_name='analytics')
    
    # Enrollment Stats
    total_enrollments = models.IntegerField(_('total enrollments'), default=0)
    active_enrollments = models.IntegerField(_('active enrollments'), default=0)
    completed_enrollments = models.IntegerField(_('completed enrollments'), default=0)
    dropout_rate = models.DecimalField(_('dropout rate'), max_digits=5, decimal_places=2, default=0)
    
    # Listening Stats
    total_listening_hours = models.DecimalField(_('total listening hours'), max_digits=10, decimal_places=2, default=0)
    avg_completion_rate = models.DecimalField(_('avg completion rate'), max_digits=5, decimal_places=2, default=0)
    total_sessions = models.IntegerField(_('total sessions'), default=0)
    
    # Engagement
    avg_session_duration = models.DecimalField(_('avg session duration (min)'), max_digits=10, decimal_places=2, default=0)
    most_popular_lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    
    # Revenue
    total_revenue = models.DecimalField(_('total revenue'), max_digits=12, decimal_places=2, default=0)
    avg_revenue_per_student = models.DecimalField(_('avg revenue per student'), max_digits=10, decimal_places=2, default=0)
    
    # Reviews
    total_reviews = models.IntegerField(_('total reviews'), default=0)
    average_rating = models.DecimalField(_('average rating'), max_digits=3, decimal_places=2, default=0)
    
    # Timestamps
    last_calculated = models.DateTimeField(_('last calculated'), auto_now=True)

    class Meta:
        verbose_name = _('course analytics')
        verbose_name_plural = _('course analytics')

    def __str__(self):
        return f"Analytics for {self.course.title}"


class TeacherAnalytics(models.Model):
    """Analytics per teacher"""
    
    teacher = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_analytics',
        limit_choices_to={'role': 'teacher'}
    )
    
    # Course Stats
    total_courses = models.IntegerField(_('total courses'), default=0)
    published_courses = models.IntegerField(_('published courses'), default=0)
    total_lessons = models.IntegerField(_('total lessons'), default=0)
    
    # Student Stats
    total_students = models.IntegerField(_('total students'), default=0)
    active_students = models.IntegerField(_('active students'), default=0)
    
    # Engagement
    total_listening_hours = models.DecimalField(_('total listening hours'), max_digits=10, decimal_places=2, default=0)
    avg_course_rating = models.DecimalField(_('avg course rating'), max_digits=3, decimal_places=2, default=0)
    total_reviews = models.IntegerField(_('total reviews'), default=0)
    
    # Revenue
    total_revenue = models.DecimalField(_('total revenue'), max_digits=12, decimal_places=2, default=0)
    avg_revenue_per_course = models.DecimalField(_('avg revenue per course'), max_digits=10, decimal_places=2, default=0)
    
    # Most Popular Course
    most_popular_course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    
    # Timestamps
    last_calculated = models.DateTimeField(_('last calculated'), auto_now=True)

    class Meta:
        verbose_name = _('teacher analytics')
        verbose_name_plural = _('teacher analytics')

    def __str__(self):
        return f"Analytics for {self.teacher.email}"


class StudentAnalytics(models.Model):
    """Analytics per student"""
    
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_analytics',
        limit_choices_to={'role': 'student'}
    )
    
    # Enrollment Stats
    total_enrollments = models.IntegerField(_('total enrollments'), default=0)
    active_enrollments = models.IntegerField(_('active enrollments'), default=0)
    completed_courses = models.IntegerField(_('completed courses'), default=0)
    
    # Learning Stats
    total_listening_hours = models.DecimalField(_('total listening hours'), max_digits=10, decimal_places=2, default=0)
    total_lessons_completed = models.IntegerField(_('total lessons completed'), default=0)
    avg_completion_rate = models.DecimalField(_('avg completion rate'), max_digits=5, decimal_places=2, default=0)
    
    # Engagement
    total_sessions = models.IntegerField(_('total sessions'), default=0)
    avg_session_duration = models.DecimalField(_('avg session duration (min)'), max_digits=10, decimal_places=2, default=0)
    total_notes = models.IntegerField(_('total notes'), default=0)
    
    # Activity
    last_active = models.DateTimeField(_('last active'), null=True, blank=True)
    current_streak = models.IntegerField(_('current streak (days)'), default=0)
    longest_streak = models.IntegerField(_('longest streak (days)'), default=0)
    
    # Spending
    total_spent = models.DecimalField(_('total spent'), max_digits=10, decimal_places=2, default=0)
    
    # Timestamps
    last_calculated = models.DateTimeField(_('last calculated'), auto_now=True)

    class Meta:
        verbose_name = _('student analytics')
        verbose_name_plural = _('student analytics')

    def __str__(self):
        return f"Analytics for {self.student.email}"

