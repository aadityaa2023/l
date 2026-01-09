from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MaxValueValidator
import uuid
import os


class AudioFile(models.Model):
    """Model to store audio file metadata"""
    
    STATUS_CHOICES = (
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    )
    
    FORMAT_CHOICES = (
        ('mp3', 'MP3'),
        ('m4a', 'M4A'),
        ('wav', 'WAV'),
        ('aac', 'AAC'),
    )
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    
    # Uploader
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_audio_files'
    )
    
    # File Details
    original_filename = models.CharField(_('original filename'), max_length=255)
    file_path = models.CharField(_('file path'), max_length=500, help_text="Path in R2/storage")
    file_format = models.CharField(_('file format'), max_length=10, choices=FORMAT_CHOICES)
    file_size = models.BigIntegerField(_('file size (bytes)'), default=0)
    
    # Audio Metadata
    duration_seconds = models.PositiveIntegerField(_('duration (seconds)'), default=0)
    bitrate = models.PositiveIntegerField(_('bitrate (kbps)'), default=0, blank=True)
    sample_rate = models.PositiveIntegerField(_('sample rate (Hz)'), default=0, blank=True)
    channels = models.PositiveSmallIntegerField(_('channels'), default=2, blank=True)
    
    # Processing Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='uploading')
    error_message = models.TextField(_('error message'), blank=True)
    
    # Security
    access_key = models.CharField(_('access key'), max_length=100, unique=True, blank=True)
    is_public = models.BooleanField(_('public'), default=False)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    last_accessed = models.DateTimeField(_('last accessed'), null=True, blank=True)

    class Meta:
        verbose_name = _('audio file')
        verbose_name_plural = _('audio files')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uploaded_by', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['access_key']),
        ]

    def __str__(self):
        return f"{self.title} ({self.original_filename})"
    
    def save(self, *args, **kwargs):
        if not self.access_key:
            self.access_key = str(uuid.uuid4())
        super().save(*args, **kwargs)


class AudioAccessLog(models.Model):
    """Log audio file access for analytics"""
    
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, related_name='access_logs')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audio_access_logs'
    )
    
    # Access Details
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.CharField(_('user agent'), max_length=500, blank=True)
    
    # Playback Info
    playback_duration = models.PositiveIntegerField(_('playback duration (seconds)'), default=0, 
                                                     help_text="How long the audio was played")
    completed = models.BooleanField(_('completed'), default=False, help_text="Did user listen to end?")
    
    # Timestamp
    accessed_at = models.DateTimeField(_('accessed at'), auto_now_add=True)

    class Meta:
        verbose_name = _('audio access log')
        verbose_name_plural = _('audio access logs')
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['audio_file', '-accessed_at']),
            models.Index(fields=['user', '-accessed_at']),
        ]

    def __str__(self):
        user_info = self.user.email if self.user else f"Anonymous ({self.ip_address})"
        return f"{self.audio_file.title} - {user_info}"


class AudioProcessingTask(models.Model):
    """Track audio processing tasks"""
    
    TASK_TYPE_CHOICES = (
        ('upload', 'Upload'),
        ('transcode', 'Transcode'),
        ('extract_metadata', 'Extract Metadata'),
        ('generate_waveform', 'Generate Waveform'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, related_name='processing_tasks')
    task_type = models.CharField(_('task type'), max_length=30, choices=TASK_TYPE_CHOICES)
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Task Details
    task_id = models.CharField(_('Celery task ID'), max_length=255, blank=True)
    progress = models.PositiveSmallIntegerField(_('progress'), default=0, validators=[MaxValueValidator(100)])
    error_message = models.TextField(_('error message'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    started_at = models.DateTimeField(_('started at'), null=True, blank=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)

    class Meta:
        verbose_name = _('audio processing task')
        verbose_name_plural = _('audio processing tasks')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_type} - {self.audio_file.title} ({self.status})"


 

