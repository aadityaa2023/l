"""
Celery tasks for analytics and background processing
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Count, Sum, Avg, F
import logging

logger = logging.getLogger(__name__)


@shared_task
def calculate_daily_analytics():
    """Calculate daily analytics for all users and courses"""
    from apps.analytics.models import (
        DailyAnalytics, ListeningSession,
        StudentAnalytics, TeacherAnalytics, CourseAnalytics
    )
    from apps.users.models import User
    from apps.courses.models import Course
    
    yesterday = timezone.now().date() - timedelta(days=1)
    
    # Calculate daily analytics
    sessions = ListeningSession.objects.filter(
        started_at__date=yesterday
    )
    
    total_listening_time = sessions.aggregate(
        total=Sum('duration')
    )['total'] or 0
    
    unique_users = sessions.values('user').distinct().count()
    total_sessions = sessions.count()
    
    DailyAnalytics.objects.create(
        date=yesterday,
        total_listening_time=total_listening_time,
        unique_users=unique_users,
        total_sessions=total_sessions
    )
    
    logger.info(f"Daily analytics calculated for {yesterday}")
    return f"Processed {total_sessions} sessions"


@shared_task
def update_course_analytics():
    """Update analytics for all courses"""
    from apps.analytics.models import CourseAnalytics, ListeningSession
    from apps.courses.models import Course, Enrollment
    
    courses = Course.objects.filter(status='published')
    
    for course in courses:
        # Get or create analytics
        analytics, created = CourseAnalytics.objects.get_or_create(course=course)
        
        # Calculate metrics
        enrollments = Enrollment.objects.filter(course=course, status='active')
        analytics.total_enrollments = enrollments.count()
        
        sessions = ListeningSession.objects.filter(lesson__module__course=course)
        analytics.total_listening_time = sessions.aggregate(
            total=Sum('duration')
        )['total'] or 0
        
        # Completion rate
        from apps.courses.models import LessonProgress
        total_lessons = course.modules.aggregate(
            total=Count('lessons')
        )['total'] or 1
        
        completed_count = LessonProgress.objects.filter(
            enrollment__course=course,
            completed=True
        ).count()
        
        analytics.completion_rate = (completed_count / (total_lessons * analytics.total_enrollments)) * 100 if analytics.total_enrollments > 0 else 0
        
        # Average rating
        from apps.courses.models import Review
        analytics.average_rating = Review.objects.filter(course=course).aggregate(
            avg=Avg('rating')
        )['avg'] or 0
        
        analytics.save()
    
    logger.info(f"Course analytics updated for {courses.count()} courses")
    return f"Updated {courses.count()} courses"


@shared_task
def update_student_analytics():
    """Update analytics for all students"""
    from apps.analytics.models import StudentAnalytics, ListeningSession
    from apps.users.models import User
    from apps.courses.models import Enrollment, LessonProgress
    
    students = User.objects.filter(is_active=True)
    
    for student in students:
        # Get or create analytics
        analytics, created = StudentAnalytics.objects.get_or_create(student=student)
        
        # Calculate metrics
        analytics.courses_enrolled = Enrollment.objects.filter(
            student=student,
            status='active'
        ).count()
        
        analytics.courses_completed = Enrollment.objects.filter(
            student=student,
            status='active',
            progress_percentage=100
        ).count()
        
        sessions = ListeningSession.objects.filter(user=student)
        analytics.total_listening_time = sessions.aggregate(
            total=Sum('duration')
        )['total'] or 0
        
        analytics.lessons_completed = LessonProgress.objects.filter(
            enrollment__student=student,
            completed=True
        ).count()
        
        # Current streak
        today = timezone.now().date()
        streak = 0
        check_date = today
        
        while True:
            has_activity = ListeningSession.objects.filter(
                user=student,
                started_at__date=check_date
            ).exists()
            
            if has_activity:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        analytics.current_streak = streak
        analytics.save()
    
    logger.info(f"Student analytics updated for {students.count()} students")
    return f"Updated {students.count()} students"


@shared_task
def update_teacher_analytics():
    """Update analytics for all teachers"""
    from apps.analytics.models import TeacherAnalytics
    from apps.users.models import User
    from apps.courses.models import Course, Enrollment, Review
    from apps.payments.models import Payment
    
    teachers = User.objects.filter(role='teacher', is_active=True)
    
    for teacher in teachers:
        # Get or create analytics
        analytics, created = TeacherAnalytics.objects.get_or_create(teacher=teacher)
        
        # Calculate metrics
        courses = Course.objects.filter(teacher=teacher)
        analytics.total_courses = courses.count()
        
        analytics.total_students = Enrollment.objects.filter(
            course__teacher=teacher,
            status='active'
        ).values('student').distinct().count()
        
        analytics.total_revenue = Payment.objects.filter(
            course__teacher=teacher,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        analytics.average_rating = Review.objects.filter(
            course__teacher=teacher
        ).aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Monthly revenue
        thirty_days_ago = timezone.now() - timedelta(days=30)
        analytics.monthly_revenue = Payment.objects.filter(
            course__teacher=teacher,
            status='completed',
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        analytics.save()
    
    logger.info(f"Teacher analytics updated for {teachers.count()} teachers")
    return f"Updated {teachers.count()} teachers"


@shared_task
def send_pending_notifications():
    """Send all pending email notifications"""
    from apps.notifications.models import Notification
    from django.core.mail import send_mail
    from django.conf import settings
    
    pending_notifications = Notification.objects.filter(
        sent=False,
        notification_type='email'
    )[:100]  # Process 100 at a time
    
    sent_count = 0
    
    for notification in pending_notifications:
        try:
            send_mail(
                subject=notification.title,
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.user.email],
                fail_silently=False
            )
            
            notification.sent = True
            notification.sent_at = timezone.now()
            notification.save()
            sent_count += 1
            
        except Exception as e:
            logger.error(f"Failed to send notification {notification.id}: {e}")
    
    logger.info(f"Sent {sent_count} notifications")
    return f"Sent {sent_count} notifications"


@shared_task
def process_audio_files():
    """Process pending audio processing tasks"""
    from apps.notifications.audio.models import AudioProcessingTask, AudioFile
    from apps.notifications.audio.utils import extract_audio_metadata
    
    pending_tasks = AudioProcessingTask.objects.filter(status='pending')[:10]
    
    processed_count = 0
    
    for task in pending_tasks:
        try:
            task.status = 'processing'
            task.save()
            
            # Extract metadata
            audio_file = task.audio_file
            metadata = extract_audio_metadata(audio_file.file.path)
            
            if metadata:
                audio_file.duration = metadata.get('duration', 0)
                audio_file.bitrate = metadata.get('bitrate', 0)
                audio_file.sample_rate = metadata.get('sample_rate', 0)
                audio_file.channels = metadata.get('channels', 2)
                audio_file.save()
                
                task.status = 'completed'
                task.completed_at = timezone.now()
            else:
                task.status = 'failed'
                task.error_message = 'Failed to extract metadata'
            
            task.save()
            processed_count += 1
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
            logger.error(f"Failed to process audio task {task.id}: {e}")
    
    logger.info(f"Processed {processed_count} audio tasks")
    return f"Processed {processed_count} audio tasks"


@shared_task
def cleanup_old_sessions():
    """Clean up old listening sessions (older than 1 year)"""
    from apps.analytics.models import ListeningSession
    
    one_year_ago = timezone.now() - timedelta(days=365)
    
    deleted_count = ListeningSession.objects.filter(
        started_at__lt=one_year_ago
    ).delete()[0]
    
    logger.info(f"Deleted {deleted_count} old sessions")
    return f"Deleted {deleted_count} old sessions"


@shared_task
def send_course_reminders():
    """Send reminders to students who haven't accessed their courses in 7 days"""
    from apps.courses.models import Enrollment
    from apps.analytics.models import ListeningSession
    from apps.notifications.models import Notification
    
    seven_days_ago = timezone.now() - timedelta(days=7)
    
    # Find enrollments with no recent activity
    enrollments = Enrollment.objects.filter(
        is_active=True,
        enrolled_at__lt=seven_days_ago
    ).select_related('student', 'course')
    
    reminder_count = 0
    
    for enrollment in enrollments:
        # Check if student has any recent sessions
        recent_sessions = ListeningSession.objects.filter(
            user=enrollment.student,
            lesson__module__course=enrollment.course,
            started_at__gte=seven_days_ago
        ).exists()
        
        if not recent_sessions:
            # Create reminder notification
            Notification.objects.create(
                user=enrollment.student,
                title=f"Continue learning: {enrollment.course.title}",
                message=f"You haven't accessed {enrollment.course.title} in a while. Continue your learning journey!",
                notification_type='email',
                category='reminder'
            )
            reminder_count += 1
    
    logger.info(f"Sent {reminder_count} course reminders")
    return f"Sent {reminder_count} course reminders"
