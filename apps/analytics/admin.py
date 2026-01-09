from django.contrib import admin
from unfold.admin import ModelAdmin
from django.utils.translation import gettext_lazy as _
from .models import ListeningSession, DailyAnalytics, CourseAnalytics, TeacherAnalytics, StudentAnalytics

# All analytics-related models are hidden from Django admin
# Superadmin uses /platformadmin/ for analytics

# @admin.register(ListeningSession)
class ListeningSessionAdmin(ModelAdmin):
    list_display = ('user', 'lesson', 'duration_seconds', 'completed', 'started_at', 'ended_at')
    list_filter = ('completed', 'started_at', 'ended_at')
    search_fields = ('user__email', 'lesson__title', 'session_id')
    readonly_fields = ('session_id', 'started_at', 'ended_at')
    
    # Unfold customizations
    list_filter_submit = True
    list_fullwidth = True
    
    fieldsets = (
        (_('Session Information'), {'fields': ('user', 'lesson', 'enrollment', 'session_id')}),
        (_('Session Details'), {'fields': ('started_at', 'ended_at', 'duration_seconds')}),
        (_('Playback Info'), {'fields': ('start_position', 'end_position', 'completed')}),
        (_('Device & Location'), {'fields': ('device_type', 'browser', 'ip_address')}),
    )


# @admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(ModelAdmin):
    list_display = ('date', 'total_active_users', 'new_enrollments', 'total_listening_hours', 'total_revenue')
    list_filter = ('date',)
    search_fields = ('date',)
    readonly_fields = ('created_at', 'updated_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Date'), {'fields': ('date',)}),
        (_('User Metrics'), {'fields': ('total_active_users', 'new_users', 'total_students', 'total_teachers')}),
        (_('Course Metrics'), {'fields': ('total_courses', 'new_courses', 'total_lessons')}),
        (_('Enrollment Metrics'), {'fields': ('total_enrollments', 'new_enrollments', 'active_enrollments')}),
        (_('Listening Metrics'), {'fields': ('total_listening_hours', 'total_sessions', 'avg_session_duration')}),
        (_('Revenue Metrics'), {'fields': ('total_revenue', 'total_payments', 'successful_payments')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# @admin.register(CourseAnalytics)
class CourseAnalyticsAdmin(ModelAdmin):
    list_display = (
        'course',
        'total_enrollments',
        'active_enrollments',
        'total_listening_hours',
        'average_rating',
    )
    list_filter = ('last_calculated',)
    search_fields = ('course__title',)
    readonly_fields = ('last_calculated',)

    # Unfold customizations
    list_filter_submit = True

    fieldsets = (
        (_('Course'), {'fields': ('course',)}),
        (_('Enrollment Stats'), {'fields': ('total_enrollments', 'active_enrollments', 'completed_enrollments', 'dropout_rate')}),
        (_('Listening Stats'), {'fields': ('total_listening_hours', 'avg_completion_rate', 'total_sessions', 'avg_session_duration', 'most_popular_lesson')}),
        (_('Revenue'), {'fields': ('total_revenue', 'avg_revenue_per_student')}),
        (_('Review Stats'), {'fields': ('total_reviews', 'average_rating')}),
        (_('Timestamps'), {'fields': ('last_calculated',)}),
    )


# @admin.register(TeacherAnalytics)
class TeacherAnalyticsAdmin(ModelAdmin):
    list_display = ('teacher', 'total_courses', 'published_courses', 'total_students', 'avg_course_rating', 'total_revenue')
    list_filter = ('last_calculated',)
    search_fields = ('teacher__email',)
    readonly_fields = ('last_calculated',)
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Teacher'), {'fields': ('teacher',)}),
        (_('Course Stats'), {'fields': ('total_courses', 'published_courses', 'total_lessons')}),
        (_('Student Stats'), {'fields': ('total_students', 'active_students')}),
        (_('Engagement'), {'fields': ('total_listening_hours', 'avg_course_rating', 'total_reviews')}),
        (_('Revenue'), {'fields': ('total_revenue', 'avg_revenue_per_course', 'most_popular_course')}),
        (_('Timestamps'), {'fields': ('last_calculated',)}),
    )


# @admin.register(StudentAnalytics)
class StudentAnalyticsAdmin(ModelAdmin):
    list_display = ('student', 'total_enrollments', 'completed_courses', 'total_listening_hours', 'current_streak', 'last_active')
    list_filter = ('last_active', 'last_calculated')
    search_fields = ('student__email',)
    readonly_fields = ('last_calculated',)
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Student'), {'fields': ('student',)}),
        (_('Enrollment Stats'), {'fields': ('total_enrollments', 'active_enrollments', 'completed_courses')}),
        (_('Learning Stats'), {'fields': ('total_listening_hours', 'total_lessons_completed', 'avg_completion_rate')}),
        (_('Engagement'), {'fields': ('total_sessions', 'avg_session_duration', 'total_notes')}),
        (_('Activity'), {'fields': ('last_active', 'current_streak', 'longest_streak')}),
        (_('Spending'), {'fields': ('total_spent',)}),
        (_('Timestamps'), {'fields': ('last_calculated',)}),
    )
