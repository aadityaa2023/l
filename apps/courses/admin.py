from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.decorators import display
from django.utils.translation import gettext_lazy as _
from django.db import models
from .models import (
    Category, Course, Module, Lesson, LessonMedia, Enrollment, 
    LessonProgress, Note, Review, Announcement
)

# All course-related models are hidden from Django admin
# Superadmin uses /platformadmin/ for course management

# @admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    list_filter_submit = True


class ModuleInline(TabularInline):
    model = Module
    extra = 1
    fields = ('title', 'order', 'is_published')


class LessonMediaInline(TabularInline):
    model = LessonMedia
    extra = 1
    fields = ('media_type', 'title', 'media_file', 'duration_seconds', 'order')
    verbose_name = "Media File"
    verbose_name_plural = "Media Files"


class LessonInline(TabularInline):
    model = Lesson
    extra = 1
    fields = ('title', 'lesson_type', 'order', 'is_published', 'is_free_preview')


# @admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ('title', 'teacher', 'category', 'status', 'price', 'total_enrollments', 'average_rating', 'created_at')
    list_filter = ('status', 'level', 'is_featured', 'is_free', 'created_at')
    search_fields = ('title', 'description', 'teacher__email')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('total_lessons', 'total_enrollments', 'average_rating', 'total_reviews', 'created_at', 'updated_at', 'published_at')
    inlines = [ModuleInline]
    
    # Unfold customizations
    list_filter_submit = True
    list_fullwidth = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    
    fieldsets = (
        (_('Basic Information'), {'fields': ('title', 'slug', 'description', 'short_description')}),
        (_('Relations'), {'fields': ('teacher', 'category')}),
        (_('Media'), {'fields': ('thumbnail', 'intro_video_url')}),
        (_('Course Details'), {'fields': ('level', 'language', 'duration_hours')}),
        (_('Pricing'), {'fields': ('price', 'discount_price', 'is_free')}),
        (_('Settings'), {'fields': ('status', 'is_featured', 'allow_download')}),
        (_('SEO'), {'fields': ('meta_title', 'meta_description', 'keywords'), 'classes': ('collapse',)}),
        (_('Statistics'), {'fields': ('total_lessons', 'total_enrollments', 'average_rating', 'total_reviews')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at', 'published_at')}),
    )
    
    actions = ['publish_courses', 'unpublish_courses', 'feature_courses']
    
    def publish_courses(self, request, queryset):
        queryset.update(status='published')
        self.message_user(request, f"{queryset.count()} courses published.")
    publish_courses.short_description = "Publish selected courses"
    
    def unpublish_courses(self, request, queryset):
        queryset.update(status='draft')
        self.message_user(request, f"{queryset.count()} courses unpublished.")
    unpublish_courses.short_description = "Unpublish selected courses"
    
    def feature_courses(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, f"{queryset.count()} courses featured.")
    feature_courses.short_description = "Feature selected courses"


# @admin.register(Module)
class ModuleAdmin(ModelAdmin):
    list_display = ('title', 'course', 'order', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'course__title')
    inlines = [LessonInline]
    list_filter_submit = True


# @admin.register(Lesson)
class LessonAdmin(ModelAdmin):
    list_display = ('title', 'slug', 'module', 'course', 'lesson_type', 'order', 'duration_seconds', 'is_published', 'is_free_preview')
    list_filter = ('lesson_type', 'is_published', 'is_free_preview', 'created_at')
    search_fields = ('title', 'slug', 'module__title', 'course__title')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {"slug": ("title",)}
    inlines = [LessonMediaInline]
    
    # Unfold customizations
    list_filter_submit = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    
    fieldsets = (
        (_('Basic Information'), {'fields': ('module', 'course', 'title', 'slug', 'description', 'lesson_type', 'order')}),
        (_('Audio Details'), {'fields': ('audio_file', 'duration_seconds', 'file_size')}),
        (_('Content'), {'fields': ('text_content',)}),
        (_('Settings'), {'fields': ('is_free_preview', 'is_published')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# @admin.register(LessonMedia)
class LessonMediaAdmin(ModelAdmin):
    list_display = ('lesson', 'media_type', 'title', 'duration_seconds', 'file_size', 'order', 'created_at')
    list_filter = ('media_type', 'created_at')
    search_fields = ('lesson__title', 'title')
    readonly_fields = ('created_at', 'updated_at')
    list_filter_submit = True
    
    fieldsets = (
        (_('Basic Information'), {'fields': ('lesson', 'media_type', 'title', 'order')}),
        (_('Media File'), {'fields': ('media_file', 'duration_seconds', 'file_size')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# @admin.register(Enrollment)
class EnrollmentAdmin(ModelAdmin):
    list_display = ('student', 'course', 'status', 'progress_percentage', 'enrolled_at', 'last_accessed')
    list_filter = ('status', 'enrolled_at')
    search_fields = ('student__email', 'course__title')
    readonly_fields = ('enrolled_at', 'last_accessed', 'progress_percentage', 'lessons_completed')
    list_filter_submit = True
    list_filter_submit = True
    
    fieldsets = (
        (_('Enrollment'), {'fields': ('student', 'course', 'status')}),
        (_('Progress'), {'fields': ('progress_percentage', 'lessons_completed', 'total_listening_time')}),
        (_('Payment'), {'fields': ('payment_amount', 'payment_reference')}),
        (_('Dates'), {'fields': ('enrolled_at', 'completed_at', 'expires_at', 'last_accessed')}),
    )


# @admin.register(LessonProgress)
class LessonProgressAdmin(ModelAdmin):
    list_display = ('enrollment', 'lesson', 'is_completed', 'completion_percentage', 'last_accessed')
    list_filter = ('is_completed', 'last_accessed')
    search_fields = ('enrollment__student__email', 'lesson__title')
    readonly_fields = ('first_accessed', 'last_accessed', 'completed_at')
    list_filter_submit = True


# @admin.register(Note)
class NoteAdmin(ModelAdmin):
    list_display = ('enrollment', 'lesson', 'timestamp_seconds', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('enrollment__student__email', 'lesson__title', 'content')
    readonly_fields = ('created_at', 'updated_at')
    list_filter_submit = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }


# @admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ('student', 'course', 'rating', 'is_approved', 'created_at')
    list_filter = ('rating', 'is_approved', 'created_at')
    search_fields = ('student__email', 'course__title', 'title', 'comment')
    readonly_fields = ('created_at', 'updated_at')
    list_filter_submit = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }
    
    actions = ['approve_reviews', 'disapprove_reviews']
    
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} reviews approved.")
    approve_reviews.short_description = "Approve selected reviews"
    
    def disapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, f"{queryset.count()} reviews disapproved.")
    disapprove_reviews.short_description = "Disapprove selected reviews"


# @admin.register(Announcement)
class AnnouncementAdmin(ModelAdmin):
    list_display = ('title', 'course', 'teacher', 'is_published', 'send_email', 'created_at')
    list_filter = ('is_published', 'send_email', 'created_at')
    search_fields = ('title', 'message', 'course__title')
    readonly_fields = ('created_at', 'updated_at')
    list_filter_submit = True
    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }

