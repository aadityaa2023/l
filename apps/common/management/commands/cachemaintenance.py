"""
Management command for cache maintenance and cleanup
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.common.cache_signals import cleanup_expired_cache, scheduled_cache_warmup
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Perform cache maintenance tasks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['cleanup', 'warmup', 'both'],
            default='both',
            help='Maintenance action to perform (default: both)'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        verbose = options['verbose']
        
        if verbose:
            self.stdout.write(
                self.style.SUCCESS(f'Starting cache maintenance: {action}')
            )
        
        try:
            if action in ['cleanup', 'both']:
                if verbose:
                    self.stdout.write('Cleaning up expired cache entries...')
                
                deleted_count = cleanup_expired_cache()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Cleaned up {deleted_count} expired cache entries'
                    )
                )
            
            if action in ['warmup', 'both']:
                if verbose:
                    self.stdout.write('Warming up cache with fresh data...')
                
                scheduled_cache_warmup()
                
                self.stdout.write(
                    self.style.SUCCESS('✓ Cache warm-up completed')
                )
            
            if verbose:
                self.stdout.write(
                    self.style.SUCCESS('Cache maintenance completed successfully!')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Cache maintenance failed: {str(e)}')
            )
            logger.error(f'Cache maintenance failed: {str(e)}', exc_info=True)