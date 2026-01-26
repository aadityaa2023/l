"""
Cache invalidation signals for automatic cache management
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.conf import settings
from apps.courses.models import Course, Category, Enrollment, Review
from apps.common.cache_utils import invalidate_cache_pattern, FragmentCacheHelper
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Course)
@receiver(post_delete, sender=Course)
def invalidate_course_cache(sender, instance, **kwargs):
    """Invalidate cache when course data changes"""
    try:
        # Invalidate specific course caches
        cache.delete(f"{settings.CACHE_KEYS['COURSE_DETAIL']}:stats:course:{instance.id}")
        cache.delete(f"{settings.CACHE_KEYS['COURSE_DETAIL']}:related:category:{instance.category.id}")
        
        # Invalidate course list caches
        cache.delete(f"{settings.CACHE_KEYS['COURSE_LIST']}:popular")
        cache.delete(f"{settings.CACHE_KEYS['HOME_TRENDING']}:all")
        
        if hasattr(instance, 'is_featured') and instance.is_featured:
            cache.delete(f"{settings.CACHE_KEYS['HOME_FEATURED']}:all")
        
        # Invalidate category-specific caches
        cache.delete(f"{settings.CACHE_KEYS['CATEGORY_LIST']}:with_courses")
        
        # Invalidate template fragments
        FragmentCacheHelper.invalidate_fragment('course_card', instance.id, instance.updated_at)
        FragmentCacheHelper.invalidate_fragment('featured_courses_section')
        FragmentCacheHelper.invalidate_fragment('trending_courses_section')
        
        logger.info(f'Cache invalidated for course: {instance.title}')
        
    except Exception as e:
        logger.error(f'Failed to invalidate course cache for {instance.title}: {str(e)}')


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def invalidate_category_cache(sender, instance, **kwargs):
    """Invalidate cache when category data changes"""
    try:
        # Invalidate category caches
        cache.delete(f"{settings.CACHE_KEYS['CATEGORY_LIST']}:active")
        cache.delete(f"{settings.CACHE_KEYS['CATEGORY_LIST']}:with_courses")
        
        # Invalidate template fragments
        FragmentCacheHelper.invalidate_fragment('category_section', instance.id, instance.updated_at)
        
        logger.info(f'Cache invalidated for category: {instance.name}')
        
    except Exception as e:
        logger.error(f'Failed to invalidate category cache for {instance.name}: {str(e)}')


@receiver(post_save, sender=Enrollment)
@receiver(post_delete, sender=Enrollment)
def invalidate_enrollment_cache(sender, instance, **kwargs):
    """Invalidate cache when enrollment data changes"""
    try:
        # Invalidate user-specific caches
        cache_key = f"{settings.CACHE_KEYS['USER_ENROLLMENTS']}:user:{instance.student.id}:course:{instance.course.id}"
        cache.delete(cache_key)
        
        # Invalidate course stats
        cache.delete(f"{settings.CACHE_KEYS['COURSE_DETAIL']}:stats:course:{instance.course.id}")
        
        # Invalidate trending courses (based on enrollment count)
        cache.delete(f"{settings.CACHE_KEYS['HOME_TRENDING']}:all")
        
        # Invalidate platform stats
        cache.delete(f"{settings.CACHE_KEYS['HOME_STATS']}:platform")
        FragmentCacheHelper.invalidate_fragment('platform_stats')
        
        logger.info(f'Cache invalidated for enrollment: {instance.student.email} -> {instance.course.title}')
        
    except Exception as e:
        logger.error(f'Failed to invalidate enrollment cache: {str(e)}')


@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def invalidate_review_cache(sender, instance, **kwargs):
    """Invalidate cache when review data changes"""
    try:
        # Invalidate course-specific caches
        cache.delete(f"{settings.CACHE_KEYS['COURSE_DETAIL']}:reviews:course:{instance.course.id}")
        cache.delete(f"{settings.CACHE_KEYS['COURSE_DETAIL']}:stats:course:{instance.course.id}")
        
        # Invalidate platform stats (satisfaction rate)
        cache.delete(f"{settings.CACHE_KEYS['HOME_STATS']}:platform")
        FragmentCacheHelper.invalidate_fragment('platform_stats')
        
        # Invalidate course card fragment (rating changed)
        FragmentCacheHelper.invalidate_fragment('course_card', instance.course.id, instance.course.updated_at)
        
        logger.info(f'Cache invalidated for review: {instance.course.title}')
        
    except Exception as e:
        logger.error(f'Failed to invalidate review cache: {str(e)}')


# Scheduled cache warming (to be used with Celery tasks)
def scheduled_cache_warmup():
    """Function to be called by scheduled tasks to warm up cache"""
    from apps.common.cache_utils import warm_homepage_data, warm_course_data
    
    try:
        warm_homepage_data()
        warm_course_data()
        logger.info('Scheduled cache warm-up completed successfully')
    except Exception as e:
        logger.error(f'Scheduled cache warm-up failed: {str(e)}')


# Cache maintenance function
def cleanup_expired_cache():
    """Clean up expired cache entries (for database cache)"""
    try:
        from django.db import connection
        
        cache_table = settings.CACHES['default']['LOCATION']
        
        with connection.cursor() as cursor:
            # Delete expired entries
            cursor.execute(f"""
                DELETE FROM {cache_table} 
                WHERE expires <= %s
            """, [connection.ops.adapt_datetimefield_value(
                connection.ops.value_to_db_datetime(
                    settings.USE_TZ and 
                    connection.timezone.localize(connection.timezone.now()) 
                    or connection.timezone.now()
                )
            )])
            
            deleted_count = cursor.rowcount
            logger.info(f'Cleaned up {deleted_count} expired cache entries')
            
        return deleted_count
        
    except Exception as e:
        logger.error(f'Cache cleanup failed: {str(e)}')
        return 0