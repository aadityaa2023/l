from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


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
