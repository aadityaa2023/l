from django.contrib import admin
from unfold.admin import ModelAdmin
from django.utils.translation import gettext_lazy as _
from .models import AudioFile, AudioAccessLog, AudioProcessingTask

# All audio-related models are hidden from Django admin
# Superadmin uses /platformadmin/ for audio management

# @admin.register(AudioFile)
class AudioFileAdmin(ModelAdmin):
    list_display = ('title', 'uploaded_by', 'file_format', 'status', 'duration_seconds', 'file_size', 'is_public', 'created_at')
    list_filter = ('status', 'file_format', 'is_public', 'created_at')
    search_fields = ('title', 'description', 'uploaded_by__email', 'original_filename')
    readonly_fields = ('id', 'access_key', 'created_at', 'updated_at', 'last_accessed')
    
    # Unfold customizations
    list_filter_submit = True
    list_fullwidth = True
    
    fieldsets = (
        (_('Basic Information'), {'fields': ('title', 'description', 'uploaded_by')}),
        (_('File Details'), {'fields': ('original_filename', 'file_path', 'file_format', 'file_size')}),
        (_('Audio Metadata'), {'fields': ('duration_seconds', 'bitrate', 'sample_rate', 'channels')}),
        (_('Status'), {'fields': ('status', 'error_message')}),
        (_('Security'), {'fields': ('access_key', 'is_public')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at', 'last_accessed')}),
    )


# @admin.register(AudioAccessLog)
class AudioAccessLogAdmin(ModelAdmin):
    list_display = ('audio_file', 'user', 'playback_duration', 'completed', 'ip_address', 'accessed_at')
    list_filter = ('completed', 'accessed_at')
    search_fields = ('audio_file__title', 'user__email', 'ip_address')
    readonly_fields = ('accessed_at',)
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Audio File'), {'fields': ('audio_file', 'user')}),
        (_('Access Details'), {'fields': ('ip_address', 'user_agent')}),
        (_('Playback Info'), {'fields': ('playback_duration', 'completed')}),
        (_('Timestamp'), {'fields': ('accessed_at',)}),
    )


# @admin.register(AudioProcessingTask)
class AudioProcessingTaskAdmin(ModelAdmin):
    list_display = ('audio_file', 'task_type', 'status', 'progress', 'created_at', 'completed_at')
    list_filter = ('task_type', 'status', 'created_at')
    search_fields = ('audio_file__title', 'task_id')
    readonly_fields = ('created_at', 'started_at', 'completed_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Task Info'), {'fields': ('audio_file', 'task_type', 'task_id')}),
        (_('Status'), {'fields': ('status', 'progress', 'error_message')}),
        (_('Timestamps'), {'fields': ('created_at', 'started_at', 'completed_at')}),
    )
