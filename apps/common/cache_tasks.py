"""
Celery periodic tasks for cache management and optimization
Provides scheduled cache warming, cleanup, and optimization
"""
from celery import shared_task
from django.core.cache import cache, caches
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg, Q
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def warm_homepage_cache(self):
    """Warm homepage cache data - runs every 30 minutes"""
    try:
        from apps.courses.models import Course, Category
        from apps.common.query_optimization import get_optimized_course_queryset
        
        # Trending courses
        trending = list(get_optimized_course_queryset(
            order_by='popular',
            limit=20
        ))
        cache.set(
            f"{settings.CACHE_KEYS['HOME_TRENDING']}:scheduled",
            trending,
            settings.CACHE_TTL.get('FREQUENT', 300)
        )
        
        # Featured courses
        featured = list(get_optimized_course_queryset(
            filters={'featured': True},
            limit=15
        ))
        cache.set(
            f"{settings.CACHE_KEYS['HOME_FEATURED']}:scheduled",
            featured,
            settings.CACHE_TTL.get('SEMI_STATIC', 7200)
        )
        
        logger.info("Homepage cache warming completed via Celery")
        return {'status': 'success', 'message': 'Homepage cache warmed'}
        
    except Exception as exc:
        logger.error(f"Homepage cache warming failed: {str(exc)}")
        # Retry after 5 minutes with exponential backoff
        raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def warm_category_cache(self):
    """Warm category and course cache - runs every hour"""
    try:
        from apps.courses.models import Category
        from apps.common.query_optimization import get_optimized_categories_with_courses
        
        categories_data = get_optimized_categories_with_courses(max_courses_per_category=20)
        cache.set(
            f"{settings.CACHE_KEYS['CATEGORY_LIST']}:scheduled",
            categories_data,
            settings.CACHE_TTL.get('SEMI_STATIC', 7200)
        )
        
        logger.info("Category cache warming completed via Celery")
        return {'status': 'success', 'message': 'Category cache warmed'}
        
    except Exception as exc:
        logger.error(f"Category cache warming failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))


@shared_task
def cleanup_expired_cache():
    """Clean up expired cache entries - runs every 6 hours"""
    try:
        from django.core.cache.backends.db import BaseDatabaseCache
        from django.db import connection
        
        cache_backend = caches['default']
        
        if isinstance(cache_backend, BaseDatabaseCache):
            cursor = connection.cursor()
            table_name = cache_backend._table
            
            # Delete expired entries
            cursor.execute(
                f"DELETE FROM {table_name} WHERE expire_time < %s",
                [timezone.now()]
            )
            deleted_count = cursor.rowcount
            connection.commit()
            
            logger.info(f"Cleaned up {deleted_count} expired cache entries")
            return {'status': 'success', 'deleted': deleted_count}
            
    except Exception as e:
        logger.error(f"Cache cleanup failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def optimize_cache_table():
    """Optimize cache database table - runs daily at 2 AM"""
    try:
        from django.core.cache.backends.db import BaseDatabaseCache
        from django.db import connection
        
        cache_backend = caches['default']
        
        if isinstance(cache_backend, BaseDatabaseCache):
            cursor = connection.cursor()
            table_name = cache_backend._table
            
            # For MySQL
            if connection.vendor == 'mysql':
                cursor.execute(f"OPTIMIZE TABLE {table_name}")
                logger.info(f"Optimized cache table: {table_name}")
                return {'status': 'success', 'vendor': 'mysql', 'table': table_name}
                
            # For PostgreSQL
            elif connection.vendor == 'postgresql':
                cursor.execute(f"VACUUM ANALYZE {table_name}")
                logger.info(f"Vacuumed cache table: {table_name}")
                return {'status': 'success', 'vendor': 'postgresql', 'table': table_name}
                
    except Exception as e:
        logger.error(f"Cache table optimization failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def generate_cache_report():
    """Generate cache performance report - runs daily at 3 AM"""
    try:
        from django.core.cache.backends.db import BaseDatabaseCache
        from django.db import connection
        
        cache_backend = caches['default']
        stats = {
            'timestamp': timezone.now().isoformat(),
            'total_entries': 0,
            'active_entries': 0,
            'expired_entries': 0,
            'cache_size_kb': 0,
        }
        
        if isinstance(cache_backend, BaseDatabaseCache):
            cursor = connection.cursor()
            table_name = cache_backend._table
            
            try:
                # Total entries
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                stats['total_entries'] = cursor.fetchone()[0]
                
                # Expired entries
                cursor.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE expire_time < %s",
                    [timezone.now()]
                )
                stats['expired_entries'] = cursor.fetchone()[0]
                
                # Active entries
                stats['active_entries'] = stats['total_entries'] - stats['expired_entries']
                
                # Cache size
                cursor.execute(
                    f"SELECT SUM(LENGTH(value)) FROM {table_name} WHERE expire_time >= %s",
                    [timezone.now()]
                )
                size = cursor.fetchone()[0]
                stats['cache_size_kb'] = (size // 1024) if size else 0
                
                logger.info(f"Cache report: {stats}")
                return {'status': 'success', 'stats': stats}
                
            except Exception as e:
                logger.warning(f"Failed to generate cache report: {str(e)}")
                return {'status': 'error', 'message': str(e)}
                
    except Exception as e:
        logger.error(f"Cache report generation failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def warm_popular_courses_cache():
    """Warm cache with most popular courses - runs every 2 hours"""
    try:
        from apps.courses.models import Course, Enrollment
        from django.db.models import Count, Q
        
        # Get most popular courses
        popular_courses = Course.objects.filter(
            status='published'
        ).annotate(
            student_count=Count('enrollments', 
                               filter=Q(enrollments__status='active'))
        ).order_by('-student_count')[:50]
        
        cache.set(
            f"{settings.CACHE_KEYS['HOME_TRENDING']}:popular_scheduled",
            list(popular_courses),
            settings.CACHE_TTL.get('FREQUENT', 300)
        )
        
        logger.info("Popular courses cache warming completed")
        return {'status': 'success', 'count': popular_courses.count()}
        
    except Exception as e:
        logger.error(f"Popular courses cache warming failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
