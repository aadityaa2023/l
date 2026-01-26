"""
Management command to clear cache data
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache, caches
from django.conf import settings
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clear cache data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['all', 'default', 'locmem'],
            default='all',
            help='Type of cache to clear (default: all)'
        )
        
        parser.add_argument(
            '--pattern',
            type=str,
            help='Clear cache keys matching this pattern (not fully implemented for DB cache)'
        )
        
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt'
        )
    
    def handle(self, *args, **options):
        cache_type = options['type']
        pattern = options.get('pattern')
        confirm = options.get('confirm')
        
        if not confirm:
            response = input(f'Are you sure you want to clear {cache_type} cache? [y/N]: ')
            if response.lower() not in ['y', 'yes']:
                self.stdout.write('Cache clearing cancelled.')
                return
        
        try:
            if cache_type == 'all':
                # Clear all cache backends
                for alias in settings.CACHES.keys():
                    cache_backend = caches[alias]
                    
                    # Get cache file count for file-based cache
                    cache_info = self._get_cache_info(alias)
                    
                    cache_backend.clear()
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Cleared {alias} cache{cache_info}')
                    )
            else:
                # Clear specific cache
                cache_backend = caches[cache_type]
                cache_info = self._get_cache_info(cache_type)
                
                cache_backend.clear()
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Cleared {cache_type} cache{cache_info}')
                )
            
            if pattern:
                self.stdout.write(
                    self.style.WARNING(
                        f'Pattern-based clearing ({pattern}) is not fully supported. '
                        'Consider using cache versioning instead.'
                    )
                )
            
            self.stdout.write(
                self.style.SUCCESS('✅ Cache clearing completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Cache clearing failed: {str(e)}')
            )
            logger.error(f'Cache clearing failed: {str(e)}', exc_info=True)
    
    def _get_cache_info(self, alias):
        """Get cache information for reporting"""
        try:
            cache_config = settings.CACHES.get(alias, {})
            backend = cache_config.get('BACKEND', '')
            
            # For file-based cache, count files
            if 'FileBasedCache' in backend:
                location = cache_config.get('LOCATION')
                if location and Path(location).exists():
                    cache_path = Path(location)
                    file_count = len(list(cache_path.glob('*.djcache')))
                    return f' ({file_count} files)'
            
            return ''
        except Exception:
            return ''