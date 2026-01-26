"""
Database query optimization utilities for LeQ platform
"""
from django.db.models import Prefetch, Count, Avg, Q
from django.core.cache import cache
from django.conf import settings
from apps.common.cache_utils import cache_query_result
import logging

logger = logging.getLogger(__name__)


def get_optimized_course_queryset(filters=None, order_by='-created_at', limit=None):
    """
    Get optimized course queryset with proper select_related and prefetch_related
    """
    from apps.courses.models import Course
    
    queryset = Course.objects.filter(status='published').select_related(
        'teacher',
        'category',
    ).prefetch_related(
        'enrollments',
        'reviews',
    ).annotate(
        student_count=Count('enrollments', filter=Q(enrollments__status='active')),
        avg_rating=Avg('reviews__rating'),
        lesson_count=Count('modules__lessons')
    )
    
    # Apply filters if provided
    if filters:
        for key, value in filters.items():
            if value:
                if key == 'category':
                    queryset = queryset.filter(category__slug=value)
                elif key == 'teacher':
                    queryset = queryset.filter(teacher__id=value)
                elif key == 'level':
                    queryset = queryset.filter(level=value)
                elif key == 'price_range':
                    if value == 'free':
                        queryset = queryset.filter(Q(price=0) | Q(is_free=True))
                    elif value == 'paid':
                        queryset = queryset.filter(price__gt=0)
                elif key == 'featured':
                    queryset = queryset.filter(is_featured=True)
                elif key == 'search':
                    queryset = queryset.filter(
                        Q(title__icontains=value) |
                        Q(description__icontains=value) |
                        Q(teacher__first_name__icontains=value) |
                        Q(teacher__last_name__icontains=value)
                    )
    
    # Apply ordering
    if order_by == 'popular':
        queryset = queryset.order_by('-student_count', '-created_at')
    elif order_by == 'rating':
        queryset = queryset.order_by('-avg_rating', '-created_at')
    elif order_by == 'price_low':
        queryset = queryset.order_by('price', '-created_at')
    elif order_by == 'price_high':
        queryset = queryset.order_by('-price', '-created_at')
    else:
        queryset = queryset.order_by(order_by)
    
    # Apply limit
    if limit:
        queryset = queryset[:limit]
    
    return queryset


def get_optimized_categories_with_courses(max_courses_per_category=15):
    """
    Get optimized categories with their courses using proper prefetching
    """
    from apps.courses.models import Category, Course
    
    # Get all active main categories
    categories_queryset = Category.objects.filter(
        is_active=True,
        parent=None  # Only main categories
    ).order_by('display_order', 'name')
    
    # Build result with manual course limiting to avoid prefetch issues
    result = []
    for category in categories_queryset:
        courses = list(Course.objects.filter(
            status='published',
            category=category
        ).select_related('teacher', 'category').annotate(
            student_count=Count('enrollments', filter=Q(enrollments__status='active'))
        ).order_by('-created_at')[:max_courses_per_category])
        
        if courses:  # Only include categories with courses
            result.append({
                'category': category,
                'courses': courses
            })
    
    return result


def get_cached_user_enrollments(user, status='active'):
    """
    Get user's enrollments with caching
    """
    from apps.courses.models import Enrollment
    
    cache_key = f"{settings.CACHE_KEYS['USER_ENROLLMENTS']}:user:{user.id}:status:{status}"
    
    def fetch_enrollments():
        return list(Enrollment.objects.filter(
            student=user,
            status=status
        ).select_related(
            'course',
            'course__teacher',
            'course__category'
        ).prefetch_related(
            'course__modules__lessons'
        ).order_by('-enrolled_at'))
    
    return cache_query_result(
        cache_key,
        fetch_enrollments,
        timeout=settings.CACHE_TTL['DYNAMIC']
    )


def get_cached_teacher_courses(teacher, status='published'):
    """
    Get teacher's courses with caching
    """
    from apps.courses.models import Course
    
    cache_key = f"{settings.CACHE_KEYS['TEACHER_COURSES']}:teacher:{teacher.id}:status:{status}"
    
    def fetch_courses():
        return list(Course.objects.filter(
            teacher=teacher,
            status=status
        ).select_related(
            'category'
        ).prefetch_related(
            'modules__lessons',
            'enrollments'
        ).annotate(
            student_count=Count('enrollments', filter=Q(enrollments__status='active')),
            lesson_count=Count('modules__lessons'),
            total_revenue=Count('enrollments', filter=Q(enrollments__status='active')) * 0  # Placeholder
        ).order_by('-created_at'))
    
    return cache_query_result(
        cache_key,
        fetch_courses,
        timeout=settings.CACHE_TTL['SEMI_STATIC']
    )


def get_cached_course_analytics(course):
    """
    Get course analytics with caching
    """
    from apps.courses.models import Enrollment, Review
    from apps.analytics.models import ListeningSession
    
    cache_key = f"course_analytics:course:{course.id}"
    
    def fetch_analytics():
        # Get enrollment stats
        total_enrollments = Enrollment.objects.filter(course=course).count()
        active_enrollments = Enrollment.objects.filter(
            course=course, status='active'
        ).count()
        
        # Get review stats
        reviews = Review.objects.filter(course=course)
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        total_reviews = reviews.count()
        
        # Get listening stats
        total_listening_time = ListeningSession.objects.filter(
            lesson__module__course=course
        ).aggregate(total=Count('duration'))['total'] or 0
        
        return {
            'total_enrollments': total_enrollments,
            'active_enrollments': active_enrollments,
            'completion_rate': (active_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0,
            'avg_rating': avg_rating,
            'total_reviews': total_reviews,
            'total_listening_time': total_listening_time,
        }
    
    return cache_query_result(
        cache_key,
        fetch_analytics,
        timeout=settings.CACHE_TTL['FREQUENT']
    )


class OptimizedQueryMixin:
    """
    Mixin to add optimized query methods to models
    """
    
    @classmethod
    def get_popular(cls, limit=10):
        """Get popular items based on various metrics"""
        cache_key = f"{cls.__name__.lower()}_popular:{limit}"
        
        def fetch_popular():
            if hasattr(cls, 'enrollments'):
                # For Course model
                return list(cls.objects.filter(status='published')
                           .annotate(popularity=Count('enrollments'))
                           .order_by('-popularity')[:limit])
            else:
                # For other models
                return list(cls.objects.all().order_by('-created_at')[:limit])
        
        return cache_query_result(cache_key, fetch_popular)
    
    @classmethod
    def get_trending(cls, days=7, limit=10):
        """Get trending items from the last N days"""
        from datetime import timedelta
        from django.utils import timezone
        
        cache_key = f"{cls.__name__.lower()}_trending:{days}:{limit}"
        
        def fetch_trending():
            cutoff_date = timezone.now() - timedelta(days=days)
            
            if hasattr(cls, 'enrollments'):
                return list(cls.objects.filter(
                    status='published',
                    created_at__gte=cutoff_date
                ).annotate(
                    recent_enrollments=Count('enrollments', 
                                           filter=Q(enrollments__enrolled_at__gte=cutoff_date))
                ).order_by('-recent_enrollments')[:limit])
            else:
                return list(cls.objects.filter(
                    created_at__gte=cutoff_date
                ).order_by('-created_at')[:limit])
        
        return cache_query_result(cache_key, fetch_trending)


def optimize_lesson_queries(course):
    """
    Get optimized lesson data for a course
    """
    from apps.courses.models import Module, Lesson
    
    cache_key = f"course_lessons:course:{course.id}"
    
    def fetch_lessons():
        return list(Module.objects.filter(course=course)
                   .prefetch_related(
                       Prefetch(
                           'lessons',
                           queryset=Lesson.objects.select_related('module')
                           .prefetch_related('media_files')
                           .order_by('order')
                       )
                   ).order_by('order'))
    
    return cache_query_result(
        cache_key,
        fetch_lessons,
        timeout=settings.CACHE_TTL['STATIC']
    )


def get_cached_platform_stats():
    """
    Get platform-wide statistics with caching
    """
    from apps.courses.models import Course, Enrollment, Review
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    cache_key = f"{settings.CACHE_KEYS['HOME_STATS']}:platform"
    
    def fetch_stats():
        # Use subqueries for better performance
        total_students = Enrollment.objects.filter(
            status='active'
        ).values('student').distinct().count()
        
        total_courses = Course.objects.filter(status='published').count()
        
        total_instructors = User.objects.filter(role='teacher').count()
        
        avg_rating = Review.objects.filter(
            is_approved=True
        ).aggregate(avg=Avg('rating'))['avg'] or 0
        
        satisfaction_rate = int(round((avg_rating / 5.0) * 100)) if avg_rating else 0
        
        return {
            'total_students': total_students,
            'total_courses': total_courses,
            'total_instructors': total_instructors,
            'satisfaction_rate': satisfaction_rate,
        }
    
    return cache_query_result(
        cache_key,
        fetch_stats,
        timeout=settings.CACHE_TTL['FREQUENT']
    )