from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """User notifications"""
    
    TYPE_CHOICES = (
        ('enrollment', 'Enrollment'),
        ('course_update', 'Course Update'),
        ('new_lesson', 'New Lesson'),
        ('announcement', 'Announcement'),
        ('payment', 'Payment'),
        ('review', 'Review'),
        ('achievement', 'Achievement'),
        ('reminder', 'Reminder'),
        ('system', 'System'),
        ('message', 'Message'),
        ('question', 'Question'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    
    # Notification Content
    notification_type = models.CharField(_('type'), max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(_('title'), max_length=255)
    message = models.TextField(_('message'))
    
    # Optional Links
    link_url = models.CharField(_('link URL'), max_length=500, blank=True)
    link_text = models.CharField(_('link text'), max_length=100, blank=True)
    
    # Related Objects (optional)
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    # Status
    is_read = models.BooleanField(_('read'), default=False)
    is_sent = models.BooleanField(_('sent'), default=False)
    send_email = models.BooleanField(_('send email'), default=False)
    email_sent = models.BooleanField(_('email sent'), default=False)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    read_at = models.DateTimeField(_('read at'), null=True, blank=True)

    class Meta:
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class Message(models.Model):
    """Messages between students and teachers"""
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    
    # Message content
    subject = models.CharField(_('subject'), max_length=255)
    body = models.TextField(_('body'))
    
    # Related course (optional)
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages'
    )
    
    # Status
    is_read = models.BooleanField(_('read'), default=False)
    read_at = models.DateTimeField(_('read at'), null=True, blank=True)
    
    # Parent message for threading
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('message')
        verbose_name_plural = _('messages')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender.email} to {self.recipient.email}: {self.subject}"


class CourseQuestion(models.Model):
    """Q&A for courses - students ask, teachers answer"""
    
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_questions',
        limit_choices_to={'role': 'student'}
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='questions'
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='questions'
    )
    
    # Question
    title = models.CharField(_('title'), max_length=255)
    question = models.TextField(_('question'))
    
    # Status
    is_answered = models.BooleanField(_('answered'), default=False)
    is_public = models.BooleanField(_('public'), default=True, help_text="Visible to all students")
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('course question')
        verbose_name_plural = _('course questions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course', '-created_at']),
            models.Index(fields=['student', '-created_at']),
            models.Index(fields=['is_answered', '-created_at']),
        ]

    def __str__(self):
        return f"{self.student.email}: {self.title}"


class QuestionAnswer(models.Model):
    """Answers to course questions"""
    
    question = models.ForeignKey(
        CourseQuestion,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_answers'
    )
    
    # Answer
    answer = models.TextField(_('answer'))
    
    # Best answer (marked by teacher)
    is_best_answer = models.BooleanField(_('best answer'), default=False)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('question answer')
        verbose_name_plural = _('question answers')
        ordering = ['-is_best_answer', 'created_at']

    def __str__(self):
        return f"Answer by {self.user.email} to: {self.question.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Mark question as answered if this is marked as best answer
        if self.is_best_answer:
            self.question.is_answered = True
            self.question.save()
            # Unmark other answers
            QuestionAnswer.objects.filter(
                question=self.question
            ).exclude(id=self.id).update(is_best_answer=False)


class EmailTemplate(models.Model):
    """Email templates for notifications"""
    
    TEMPLATE_TYPE_CHOICES = (
        ('welcome', 'Welcome Email'),
        ('enrollment_confirmation', 'Enrollment Confirmation'),
        ('payment_success', 'Payment Success'),
        ('payment_failed', 'Payment Failed'),
        ('new_lesson', 'New Lesson'),
        ('course_announcement', 'Course Announcement'),
        ('password_reset', 'Password Reset'),
        ('email_verification', 'Email Verification'),
        ('course_completion', 'Course Completion'),
        ('reminder', 'Reminder'),
    )
    
    template_type = models.CharField(_('template type'), max_length=50, choices=TEMPLATE_TYPE_CHOICES, unique=True)
    subject = models.CharField(_('subject'), max_length=255)
    html_content = models.TextField(_('HTML content'), help_text="Use {{variable}} for dynamic content")
    text_content = models.TextField(_('text content'), help_text="Plain text version")
    
    # Settings
    is_active = models.BooleanField(_('active'), default=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('email template')
        verbose_name_plural = _('email templates')

    def __str__(self):
        return f"{self.get_template_type_display()}"


class EmailLog(models.Model):
    """Log of sent emails"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_logs')
    to_email = models.EmailField(_('to email'))
    
    # Email Content
    subject = models.CharField(_('subject'), max_length=255)
    template_type = models.CharField(_('template type'), max_length=50, blank=True)
    
    # Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(_('error message'), blank=True)
    
    # Metadata
    sent_via = models.CharField(_('sent via'), max_length=50, default='SMTP')
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    sent_at = models.DateTimeField(_('sent at'), null=True, blank=True)

    class Meta:
        verbose_name = _('email log')
        verbose_name_plural = _('email logs')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.to_email} - {self.subject} ({self.status})"

