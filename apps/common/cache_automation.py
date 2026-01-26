"""
Automated cache management and scheduling for production
Handles automatic cache warming, cleanup, and optimization
"""
import logging
from django.core.cache import caches, cache
from django.conf import settings
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
import threading
import time

logger = logging.getLogger(__name__)


class CacheAutomation:
    """Handles automated cache operations for production"""
    
    def __init__(self):
        self.cache_backend = caches['default']
        self.local_cache = caches.get('local_memory', None)
        self.running = False
        self.maintenance_thread = None
        
    def start_automation(self):
        """Start automated cache management in background thread"""
        if self.running:
            logger.warning("Cache automation already running")
            return
        
        self.running = True
        self.maintenance_thread = threading.Thread(
            target=self._automation_loop,
            daemon=True,
            name='CacheAutomationThread'
        )
        self.maintenance_thread.start()
        logger.info("Cache automation started")
        
    def stop_automation(self):
        """Stop automated cache management"""
        self.running = False
        if self.maintenance_thread:
            self.maintenance_thread.join(timeout=5)
        logger.info("Cache automation stopped")
        
    def _automation_loop(self):
        """Main automation loop - runs periodically"""
        maintenance_interval = getattr(settings, 'CACHE_MAINTENANCE_INTERVAL', 3600)  # 1 hour
        
        while self.running:
            try:
                logger.debug("Running cache maintenance cycle")
                
                # Run maintenance tasks
                self.perform_maintenance()
                
                # Check and warm cache if needed
                self.smart_cache_warming()
                
                # Cleanup expired cache entries
                self.cleanup_expired_entries()
                
                logger.debug("Cache maintenance cycle completed")
                
            except Exception as e:
                logger.error(f"Error in cache automation loop: {str(e)}", exc_info=True)
            
            # Sleep for the maintenance interval
            time.sleep(maintenance_interval)
    
    def perform_maintenance(self):
        """Perform regular cache maintenance"""
        try:
            from apps.courses.models import Course, Category
            
            cache_stats = {
                'timestamp': timezone.now(),
                'operations': 0,
                'errors': 0
            }
            
            # Get popular courses (trending)
            popular_courses = Course.objects.filter(
                status='published'
            ).annotate(
                enrollment_count=Count('enrollments', 
                                     filter=Q(enrollments__status='active'))
            ).order_by('-enrollment_count')[:50]
            
            # Get active categories
            active_categories = Category.objects.filter(
                is_active=True,
                parent=None
            ).order_by('display_order')[:20]
            
            # Cache popular courses
            cache_key = f"{settings.CACHE_KEYS['HOME_TRENDING']}:maintenance"
            cache.set(cache_key, list(popular_courses), 
                     settings.CACHE_TTL.get('SEMI_STATIC', 7200))
            cache_stats['operations'] += 1
            
            # Cache active categories
            cache_key = f"{settings.CACHE_KEYS['CATEGORY_LIST']}:maintenance"
            cache.set(cache_key, list(active_categories),
                     settings.CACHE_TTL.get('STATIC', 86400))
            cache_stats['operations'] += 1
            
            logger.info(f"Cache maintenance completed: {cache_stats['operations']} operations")
            
        except Exception as e:
            logger.error(f"Cache maintenance failed: {str(e)}")
    
    def smart_cache_warming(self):
        """Intelligently warm cache based on demand patterns"""
        try:
            from apps.courses.models import Course, Enrollment
            
            current_hour = timezone.now().hour
            
            # Warm cache during off-peak hours (2 AM - 6 AM)
            if 2 <= current_hour <= 6:
                logger.debug("Off-peak hours: performing intensive cache warming")
                self._intensive_cache_warming()
            else:
                # Light warming during peak hours
                logger.debug("Peak hours: performing light cache warming")
                self._light_cache_warming()
                
        except Exception as e:
            logger.error(f"Smart cache warming failed: {str(e)}")
    
    def _intensive_cache_warming(self):
        """Warm cache extensively during off-peak hours"""
        from apps.courses.models import Course, Category
        from apps.common.query_optimization import (
            get_optimized_course_queryset,
            get_optimized_categories_with_courses
        )
        
        try:
            # Warm homepage data
            trending = list(get_optimized_course_queryset(
                order_by='popular',
                limit=20
            ))
            cache.set(f"{settings.CACHE_KEYS['HOME_TRENDING']}:warmed",
                     trending,
                     settings.CACHE_TTL.get('FREQUENT', 300))
            
            # Warm featured courses
            featured = list(get_optimized_course_queryset(
                filters={'featured': True},
                limit=15
            ))
            cache.set(f"{settings.CACHE_KEYS['HOME_FEATURED']}:warmed",
                     featured,
                     settings.CACHE_TTL.get('SEMI_STATIC', 7200))
            
            # Warm category courses
            categories_data = get_optimized_categories_with_courses(20)
            cache.set(f"{settings.CACHE_KEYS['CATEGORY_LIST']}:warmed",
                     categories_data,
                     settings.CACHE_TTL.get('SEMI_STATIC', 7200))
            
            logger.info("Intensive cache warming completed")
            
        except Exception as e:
            logger.error(f"Intensive cache warming failed: {str(e)}")
    
    def _light_cache_warming(self):
        """Warm frequently accessed cache during peak hours"""
        try:
            cache_keys_to_warm = [
                f"{settings.CACHE_KEYS['CATEGORY_LIST']}:active",
                f"{settings.CACHE_KEYS['HOME_FEATURED']}:all",
            ]
            
            # Refresh top cache keys if they're about to expire
            for cache_key in cache_keys_to_warm:
                value = cache.get(cache_key)
                if value is None:
                    logger.debug(f"Light warming: refreshing cache key {cache_key}")
                    # Cache will be repopulated on next request
                    
        except Exception as e:
            logger.error(f"Light cache warming failed: {str(e)}")
    
    def cleanup_expired_entries(self):
        """Clean up expired cache entries"""
        try:
            # Database cache backend automatically handles expiration
            # This is more for monitoring and optimization
            
            from django.core.cache.backends.db import BaseDatabaseCache
            from django.db import connection
            
            if isinstance(self.cache_backend, BaseDatabaseCache):
                # Remove expired entries
                cursor = connection.cursor()
                table_name = self.cache_backend._table
                
                expired_count = 0
                try:
                    # Count expired entries
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table_name} WHERE expire_time < %s",
                        [timezone.now()]
                    )
                    expired_count = cursor.fetchone()[0]
                    
                    # Delete expired entries
                    cursor.execute(
                        f"DELETE FROM {table_name} WHERE expire_time < %s",
                        [timezone.now()]
                    )
                    connection.commit()
                    
                    if expired_count > 0:
                        logger.info(f"Cleaned up {expired_count} expired cache entries")
                        
                except Exception as e:
                    logger.warning(f"Cache cleanup query failed: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Cache cleanup failed: {str(e)}")
    
    def get_cache_stats(self):
        """Get current cache statistics"""
        try:
            from django.core.cache.backends.db import BaseDatabaseCache
            from django.db import connection
            
            stats = {
                'total_entries': 0,
                'expired_entries': 0,
                'active_entries': 0,
                'cache_size': 0,
                'timestamp': timezone.now().isoformat()
            }
            
            if isinstance(self.cache_backend, BaseDatabaseCache):
                cursor = connection.cursor()
                table_name = self.cache_backend._table
                
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
                    
                    # Cache size (approximate)
                    cursor.execute(
                        f"SELECT SUM(LENGTH(value)) FROM {table_name} WHERE expire_time >= %s",
                        [timezone.now()]
                    )
                    size = cursor.fetchone()[0]
                    stats['cache_size'] = size if size else 0
                    
                except Exception as e:
                    logger.warning(f"Failed to get cache stats: {str(e)}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return None
    
    def optimize_cache_table(self):
        """Optimize the cache database table"""
        try:
            from django.core.cache.backends.db import BaseDatabaseCache
            from django.db import connection
            
            if isinstance(self.cache_backend, BaseDatabaseCache):
                cursor = connection.cursor()
                table_name = self.cache_backend._table
                
                # For MySQL
                if connection.vendor == 'mysql':
                    cursor.execute(f"OPTIMIZE TABLE {table_name}")
                    logger.info(f"Optimized cache table: {table_name}")
                    
                # For PostgreSQL
                elif connection.vendor == 'postgresql':
                    cursor.execute(f"VACUUM ANALYZE {table_name}")
                    logger.info(f"Vacuumed cache table: {table_name}")
                    
        except Exception as e:
            logger.warning(f"Cache table optimization failed: {str(e)}")


# Global cache automation instance
_cache_automation = None


def get_cache_automation():
    """Get or create the cache automation instance"""
    global _cache_automation
    if _cache_automation is None:
        _cache_automation = CacheAutomation()
    return _cache_automation


def start_cache_automation():
    """Start cache automation globally"""
    automation = get_cache_automation()
    automation.start_automation()


def stop_cache_automation():
    """Stop cache automation globally"""
    automation = get_cache_automation()
    automation.stop_automation()
