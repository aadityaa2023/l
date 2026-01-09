from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget
from django.utils.translation import gettext_lazy as _
from django.db import models
from .models import Notification, EmailTemplate, EmailLog, Message, CourseQuestion, QuestionAnswer

# All notification-related models are hidden from Django admin
# Superadmin uses /platformadmin/ for notification management

# @admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'send_email', 'email_sent', 'created_at')
    list_filter = ('notification_type', 'is_read', 'send_email', 'email_sent', 'created_at')
    search_fields = ('user__email', 'title', 'message')
    readonly_fields = ('created_at', 'read_at')
    
    # Unfold customizations
    list_filter_submit = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    
    fieldsets = (
        (_('User'), {'fields': ('user',)}),
        (_('Notification Content'), {'fields': ('notification_type', 'title', 'message')}),
        (_('Links'), {'fields': ('link_url', 'link_text')}),
        (_('Related Objects'), {'fields': ('course', 'lesson')}),
        (_('Status'), {'fields': ('is_read', 'is_sent', 'send_email', 'email_sent')}),
        (_('Timestamps'), {'fields': ('created_at', 'read_at')}),
    )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f"{queryset.count()} notifications marked as read.")
    mark_as_read.short_description = "Mark selected as read"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False, read_at=None)
        self.message_user(request, f"{queryset.count()} notifications marked as unread.")
    mark_as_unread.short_description = "Mark selected as unread"


# @admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ('sender', 'recipient', 'subject', 'course', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__email', 'recipient__email', 'subject', 'body')
    readonly_fields = ('created_at', 'updated_at', 'read_at')
    
    fieldsets = (
        (_('Participants'), {'fields': ('sender', 'recipient')}),
        (_('Message'), {'fields': ('subject', 'body', 'course', 'parent')}),
        (_('Status'), {'fields': ('is_read', 'read_at')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# @admin.register(CourseQuestion)
class CourseQuestionAdmin(ModelAdmin):
    list_display = ('student', 'course', 'title', 'is_answered', 'is_public', 'created_at')
    list_filter = ('is_answered', 'is_public', 'created_at', 'course')
    search_fields = ('student__email', 'title', 'question', 'course__title')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Question Info'), {'fields': ('student', 'course', 'lesson')}),
        (_('Content'), {'fields': ('title', 'question')}),
        (_('Status'), {'fields': ('is_answered', 'is_public')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# @admin.register(QuestionAnswer)
class QuestionAnswerAdmin(ModelAdmin):
    list_display = ('user', 'question', 'is_best_answer', 'created_at')
    list_filter = ('is_best_answer', 'created_at')
    search_fields = ('user__email', 'answer', 'question__title')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Answer Info'), {'fields': ('question', 'user')}),
        (_('Content'), {'fields': ('answer', 'is_best_answer')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# @admin.register(EmailTemplate)
class EmailTemplateAdmin(ModelAdmin):
    list_display = ('template_type', 'subject', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'template_type', 'created_at')
    search_fields = ('template_type', 'subject', 'html_content', 'text_content')
    readonly_fields = ('created_at', 'updated_at')
    
    # Unfold customizations
    list_filter_submit = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    
    fieldsets = (
        (_('Template Info'), {'fields': ('template_type', 'subject')}),
        (_('Content'), {'fields': ('html_content', 'text_content')}),
        (_('Settings'), {'fields': ('is_active',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# @admin.register(EmailLog)
class EmailLogAdmin(ModelAdmin):
    list_display = ('user', 'to_email', 'subject', 'status', 'created_at', 'sent_at')
    list_filter = ('status', 'created_at', 'sent_at')
    search_fields = ('to_email', 'subject', 'template_type')
    readonly_fields = ('created_at', 'sent_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Email Info'), {'fields': ('user', 'to_email', 'subject', 'template_type')}),
        (_('Status'), {'fields': ('status', 'error_message', 'sent_via')}),
        (_('Timestamps'), {'fields': ('created_at', 'sent_at')}),
    )
