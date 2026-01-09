"""
Utility functions for Mobile API
"""
from django.db.models import Avg, Count, Q
from django.utils import timezone
from apps.courses.models import Course, Enrollment, LessonProgress


def get_recommended_courses(user, limit=10):
    """
    Get recommended courses for a user based on their enrollments and interests
    """
    if not user.is_authenticated:
        # Return popular courses for anonymous users
        return Course.objects.filter(
            status='published'
        ).order_by('-total_enrollments', '-average_rating')[:limit]
    
    # Get user's enrolled course categories
    enrolled_categories = Enrollment.objects.filter(
        student=user
    ).values_list('course__category', flat=True).distinct()
    
    # Get courses in same categories that user hasn't enrolled in
    recommended = Course.objects.filter(
        status='published',
        category__in=enrolled_categories
    ).exclude(
        enrollments__student=user
    ).order_by('-average_rating', '-total_enrollments')[:limit]
    
    # If not enough recommendations, add popular courses
    if recommended.count() < limit:
        popular = Course.objects.filter(
            status='published'
        ).exclude(
            enrollments__student=user
        ).order_by('-total_enrollments')[:limit - recommended.count()]
        
        recommended = list(recommended) + list(popular)
    
    return recommended


def calculate_course_progress(enrollment):
    """
    Calculate overall course progress percentage
    """
    total_lessons = enrollment.course.total_lessons
    
    if total_lessons == 0:
        return 0
    
    completed_lessons = LessonProgress.objects.filter(
        enrollment=enrollment,
        is_completed=True
    ).count()
    
    return round((completed_lessons / total_lessons) * 100, 2)


def update_enrollment_progress(enrollment):
    """
    Update enrollment progress statistics
    """
    # Calculate progress percentage
    enrollment.progress_percentage = calculate_course_progress(enrollment)
    
    # Count completed lessons
    enrollment.lessons_completed = LessonProgress.objects.filter(
        enrollment=enrollment,
        is_completed=True
    ).count()
    
    # Calculate total listening time
    total_time = LessonProgress.objects.filter(
        enrollment=enrollment
    ).aggregate(total=models.Sum('total_time_spent'))['total'] or 0
    
    enrollment.total_listening_time = total_time
    
    # Mark as completed if all lessons are done
    if enrollment.progress_percentage >= 100 and enrollment.status == 'active':
        enrollment.status = 'completed'
        enrollment.completed_at = timezone.now()
    
    enrollment.save()
    
    return enrollment


def get_user_learning_stats(user):
    """
    Get comprehensive learning statistics for a user
    """
    from django.db.models import Sum
    from apps.analytics.models import ListeningSession
    
    enrollments = Enrollment.objects.filter(student=user)
    
    stats = {
        'total_courses_enrolled': enrollments.count(),
        'active_courses': enrollments.filter(status='active').count(),
        'completed_courses': enrollments.filter(status='completed').count(),
        'total_lessons_completed': LessonProgress.objects.filter(
            enrollment__student=user,
            is_completed=True
        ).count(),
        'total_listening_time_seconds': enrollments.aggregate(
            total=Sum('total_listening_time')
        )['total'] or 0,
        'average_progress': enrollments.filter(
            status='active'
        ).aggregate(
            avg=Avg('progress_percentage')
        )['avg'] or 0,
        'total_listening_sessions': ListeningSession.objects.filter(
            user=user
        ).count(),
    }
    
    # Convert seconds to hours
    stats['total_listening_hours'] = round(stats['total_listening_time_seconds'] / 3600, 2)
    
    # Calculate streak (days of continuous learning)
    stats['current_streak'] = calculate_learning_streak(user)
    
    return stats


def calculate_learning_streak(user):
    """
    Calculate the number of consecutive days a user has been learning
    """
    from apps.analytics.models import ListeningSession
    from datetime import timedelta
    
    today = timezone.now().date()
    streak = 0
    current_date = today
    
    while True:
        # Check if user had any activity on current_date
        has_activity = ListeningSession.objects.filter(
            user=user,
            started_at__date=current_date
        ).exists()
        
        if has_activity:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            break
        
        # Limit to 365 days to prevent infinite loop
        if streak >= 365:
            break
    
    return streak


def search_courses(query, filters=None):
    """
    Advanced course search with filtering
    
    Args:
        query (str): Search query
        filters (dict): Filter parameters
            - category: Category ID
            - level: Course level
            - is_free: Boolean
            - min_price: Minimum price
            - max_price: Maximum price
            - min_rating: Minimum rating
            - language: Course language
    """
    courses = Course.objects.filter(status='published')
    
    # Text search
    if query:
        courses = courses.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(teacher__first_name__icontains=query) |
            Q(teacher__last_name__icontains=query)
        )
    
    # Apply filters
    if filters:
        if filters.get('category'):
            courses = courses.filter(category_id=filters['category'])
        
        if filters.get('level'):
            courses = courses.filter(level=filters['level'])
        
        if filters.get('is_free') is not None:
            courses = courses.filter(is_free=filters['is_free'])
        
        if filters.get('min_price') is not None:
            courses = courses.filter(price__gte=filters['min_price'])
        
        if filters.get('max_price') is not None:
            courses = courses.filter(price__lte=filters['max_price'])
        
        if filters.get('min_rating') is not None:
            courses = courses.filter(average_rating__gte=filters['min_rating'])
        
        if filters.get('language'):
            courses = courses.filter(language=filters['language'])
    
    return courses.select_related('teacher', 'category')


def validate_enrollment_access(user, course):
    """
    Check if user has access to a course
    
    Returns:
        tuple: (has_access, enrollment, message)
    """
    if not user.is_authenticated:
        return (False, None, "Authentication required")
    
    # Check if course is published
    if course.status != 'published':
        return (False, None, "Course not available")
    
    # Check if free course
    if course.is_free:
        enrollment, _ = Enrollment.objects.get_or_create(
            student=user,
            course=course,
            defaults={'payment_amount': 0}
        )
        return (True, enrollment, "Access granted")
    
    # Check for active enrollment
    enrollment = Enrollment.objects.filter(
        student=user,
        course=course,
        status='active'
    ).first()
    
    if enrollment:
        return (True, enrollment, "Access granted")
    
    return (False, None, "Enrollment required")


def format_duration(seconds):
    """
    Format duration in seconds to human-readable format
    
    Returns:
        str: Formatted duration (e.g., "1h 30m", "45m", "30s")
    """
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        return f"{hours}h"
    
    return f"{hours}h {remaining_minutes}m"


def get_next_lesson(enrollment, current_lesson=None):
    """
    Get the next lesson for a user in their enrollment
    
    Args:
        enrollment: Enrollment object
        current_lesson: Current lesson (optional)
    
    Returns:
        Lesson object or None
    """
    from apps.courses.models import Lesson
    
    # If no current lesson, get first lesson
    if not current_lesson:
        return Lesson.objects.filter(
            course=enrollment.course,
            is_published=True
        ).order_by('module__order', 'order').first()
    
    # Get next lesson in same module
    next_in_module = Lesson.objects.filter(
        module=current_lesson.module,
        order__gt=current_lesson.order,
        is_published=True
    ).order_by('order').first()
    
    if next_in_module:
        return next_in_module
    
    # Get first lesson of next module
    from apps.courses.models import Module
    
    next_module = Module.objects.filter(
        course=enrollment.course,
        order__gt=current_lesson.module.order,
        is_published=True
    ).order_by('order').first()
    
    if next_module:
        return Lesson.objects.filter(
            module=next_module,
            is_published=True
        ).order_by('order').first()
    
    return None


def get_course_completion_stats(course):
    """
    Get course completion statistics
    
    Returns:
        dict: Completion statistics
    """
    total_enrollments = course.enrollments.count()
    
    if total_enrollments == 0:
        return {
            'total_enrollments': 0,
            'completed_enrollments': 0,
            'completion_rate': 0,
            'average_progress': 0,
        }
    
    completed = course.enrollments.filter(status='completed').count()
    avg_progress = course.enrollments.aggregate(
        avg=Avg('progress_percentage')
    )['avg'] or 0
    
    return {
        'total_enrollments': total_enrollments,
        'completed_enrollments': completed,
        'completion_rate': round((completed / total_enrollments) * 100, 2),
        'average_progress': round(avg_progress, 2),
    }
