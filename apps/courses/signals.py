from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Avg, Count
from django.utils import timezone
from .models import Lesson, Module, Enrollment, Review, LessonProgress, Course


@receiver(post_save, sender=Lesson)
@receiver(post_delete, sender=Lesson)
def update_course_lesson_count(sender, instance, **kwargs):
    """Update total lessons count when a lesson is added or deleted"""
    course = instance.course
    course.total_lessons = course.lessons.filter(is_published=True).count()
    course.save(update_fields=['total_lessons'])


@receiver(post_save, sender=Enrollment)
@receiver(post_delete, sender=Enrollment)
def update_course_enrollment_count(sender, instance, **kwargs):
    """Update total enrollments count"""
    course = instance.course
    course.total_enrollments = course.enrollments.filter(status='active').count()
    course.save(update_fields=['total_enrollments'])


@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def update_course_rating(sender, instance, **kwargs):
    """Update course average rating and review count"""
    course = instance.course
    reviews = course.reviews.filter(is_approved=True)
    course.total_reviews = reviews.count()
    course.average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    course.save(update_fields=['total_reviews', 'average_rating'])


@receiver(post_save, sender=LessonProgress)
def update_enrollment_progress(sender, instance, created, **kwargs):
    """Update enrollment progress when lesson progress changes"""
    enrollment = instance.enrollment
    
    # Calculate completed lessons
    completed_count = enrollment.lesson_progress.filter(is_completed=True).count()
    enrollment.lessons_completed = completed_count
    
    # Calculate progress percentage
    total_lessons = enrollment.course.total_lessons
    if total_lessons > 0:
        enrollment.progress_percentage = (completed_count / total_lessons) * 100
    
    # Check if course is completed
    if enrollment.progress_percentage >= 100 and enrollment.status == 'active':
        enrollment.status = 'completed'
        enrollment.completed_at = timezone.now()
    
    enrollment.save(update_fields=['lessons_completed', 'progress_percentage', 'status', 'completed_at'])


@receiver(pre_save, sender=Course)
def set_published_date(sender, instance, **kwargs):
    """Set published date when status changes to published"""
    if instance.pk:
        try:
            old_instance = Course.objects.get(pk=instance.pk)
            if old_instance.status != 'published' and instance.status == 'published':
                instance.published_at = timezone.now()
        except Course.DoesNotExist:
            pass
