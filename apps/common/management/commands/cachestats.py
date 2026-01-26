"""
Management command to show cache statistics and health
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache, caches
from django.conf import settings
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Display cache statistics and health information'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed cache information'
        )
    
    def handle(self, *args, **options):
        detailed = options.get('detailed', False)
        
        self.stdout.write(
            self.style.SUCCESS('LeQ Cache Statistics')
        )
        self.stdout.write('=' * 50)
        
        try:
            # Show configured caches
            self.stdout.write('\nConfigured Caches:')
            for alias, config in settings.CACHES.items():
                backend = config['BACKEND'].split('.')[-1]
                timeout = config.get('TIMEOUT', 'Default')
                self.stdout.write(
                    f'  • {alias}: {backend} (timeout: {timeout}s)'
                )
            
            # Database cache statistics
            if 'default' in settings.CACHES:
                self.stdout.write('\nDatabase Cache Statistics:')
                try:
                    with connection.cursor() as cursor:
                        # Get cache table size
                        cache_table = settings.CACHES['default']['LOCATION']
                        cursor.execute(f"SELECT COUNT(*) FROM {cache_table}")
                        total_entries = cursor.fetchone()[0]
                        
                        # Get cache hits (approximate based on recent entries)
                        cursor.execute(f"""
                            SELECT COUNT(*) FROM {cache_table} 
                            WHERE expires > %s
                        """, [connection.ops.adapt_datetimefield_value(
                            connection.ops.value_to_db_datetime(
                                settings.USE_TZ and 
                                connection.timezone.localize(
                                    connection.timezone.now()
                                ) or connection.timezone.now()
                            )
                        )])
                        active_entries = cursor.fetchone()[0]
                        
                        self.stdout.write(f'  • Total entries: {total_entries}')
                        self.stdout.write(f'  • Active entries: {active_entries}')
                        self.stdout.write(f'  • Expired entries: {total_entries - active_entries}')
                        
                        if detailed:
                            # Show top cache keys by size (if supported)
                            cursor.execute(f"""
                                SELECT cache_key, LENGTH(value) as size 
                                FROM {cache_table} 
                                WHERE expires > %s 
                                ORDER BY size DESC 
                                LIMIT 10
                            """, [connection.ops.adapt_datetimefield_value(
                                connection.ops.value_to_db_datetime(
                                    settings.USE_TZ and 
                                    connection.timezone.localize(
                                        connection.timezone.now()
                                    ) or connection.timezone.now()
                                )
                            )])
                            
                            self.stdout.write('\n  Top cache keys by size:')
                            for key, size in cursor.fetchall():
                                size_kb = size / 1024
                                key_short = key[:50] + '...' if len(key) > 50 else key
                                self.stdout.write(f'    {key_short}: {size_kb:.2f} KB')
                
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Could not get database cache stats: {str(e)}'
                        )
                    )
            
            # Test cache functionality
            self.stdout.write('\nCache Health Check:')
            test_key = 'leq_cache_health_check'
            test_value = 'test_data'
            
            try:
                # Test default cache
                cache.set(test_key, test_value, 60)
                retrieved = cache.get(test_key)
                
                if retrieved == test_value:
                    self.stdout.write('  ✓ Default cache: Working')
                else:
                    self.stdout.write('  ✗ Default cache: Failed')
                
                cache.delete(test_key)
                
                # Test local memory cache
                if 'locmem' in settings.CACHES:
                    locmem_cache = caches['locmem']
                    locmem_cache.set(test_key, test_value, 60)
                    retrieved = locmem_cache.get(test_key)
                    
                    if retrieved == test_value:
                        self.stdout.write('  ✓ Local memory cache: Working')
                    else:
                        self.stdout.write('  ✗ Local memory cache: Failed')
                    
                    locmem_cache.delete(test_key)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Cache health check failed: {str(e)}')
                )
            
            # Cache configuration recommendations
            self.stdout.write('\nRecommendations:')
            
            if detailed:
                # Check for potential issues
                default_timeout = settings.CACHES.get('default', {}).get('TIMEOUT', 300)
                if default_timeout > 3600:
                    self.stdout.write(
                        '  ⚠ Consider reducing default cache timeout for dynamic content'
                    )
                
                max_entries = settings.CACHES.get('default', {}).get('OPTIONS', {}).get('MAX_ENTRIES', 300)
                if max_entries < 1000:
                    self.stdout.write(
                        '  💡 Consider increasing MAX_ENTRIES for better cache utilization'
                    )
                
                self.stdout.write(
                    '  💡 Run "python manage.py warmcache" to pre-populate cache'
                )
                self.stdout.write(
                    '  💡 Monitor cache hit rates and adjust timeouts accordingly'
                )
            
            self.stdout.write(
                self.style.SUCCESS('\nCache statistics completed!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to get cache statistics: {str(e)}')
            )
            logger.error(f'Cache statistics failed: {str(e)}', exc_info=True)