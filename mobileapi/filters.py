"""
Custom filters for Mobile API
"""
from django_filters import rest_framework as filters
from apps.courses.models import Course, Lesson, Enrollment


class CourseFilter(filters.FilterSet):
    """
    Advanced filtering for courses
    """
    min_price = filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = filters.NumberFilter(field_name='price', lookup_expr='lte')
    min_rating = filters.NumberFilter(field_name='average_rating', lookup_expr='gte')
    min_duration = filters.NumberFilter(field_name='duration_hours', lookup_expr='gte')
    max_duration = filters.NumberFilter(field_name='duration_hours', lookup_expr='lte')
    
    class Meta:
        model = Course
        fields = {
            'category': ['exact'],
            'level': ['exact'],
            'language': ['exact', 'icontains'],
            'is_free': ['exact'],
            'is_featured': ['exact'],
            'teacher': ['exact'],
        }


class LessonFilter(filters.FilterSet):
    """
    Filtering for lessons
    """
    course = filters.NumberFilter(field_name='course__id')
    module = filters.NumberFilter(field_name='module__id')
    min_duration = filters.NumberFilter(field_name='duration_seconds', lookup_expr='gte')
    max_duration = filters.NumberFilter(field_name='duration_seconds', lookup_expr='lte')
    
    class Meta:
        model = Lesson
        fields = {
            'lesson_type': ['exact'],
            'is_free_preview': ['exact'],
        }


class EnrollmentFilter(filters.FilterSet):
    """
    Filtering for enrollments
    """
    min_progress = filters.NumberFilter(field_name='progress_percentage', lookup_expr='gte')
    max_progress = filters.NumberFilter(field_name='progress_percentage', lookup_expr='lte')
    enrolled_after = filters.DateTimeFilter(field_name='enrolled_at', lookup_expr='gte')
    enrolled_before = filters.DateTimeFilter(field_name='enrolled_at', lookup_expr='lte')
    
    class Meta:
        model = Enrollment
        fields = {
            'status': ['exact'],
            'course': ['exact'],
        }
