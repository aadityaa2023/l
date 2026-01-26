"""
Management command to warm up the cache with frequently accessed data
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.conf import settings
from apps.common.cache_utils import warm_homepage_data, warm_course_data
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Warm up the cache with frequently accessed data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['homepage', 'courses', 'all'],
            default='all',
            help='Type of data to warm up (default: all)'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cache refresh even if data already exists'
        )
    
    def handle(self, *args, **options):
        cache_type = options['type']
        force = options['force']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting cache warm-up for: {cache_type}')
        )
        
        try:
            if force:
                self.stdout.write('Forcing cache refresh...')
                cache.clear()
            
            if cache_type in ['homepage', 'all']:
                self.stdout.write('Warming homepage data...')
                warm_homepage_data()
                self.stdout.write(
                    self.style.SUCCESS('✓ Homepage cache warmed successfully')
                )
            
            if cache_type in ['courses', 'all']:
                self.stdout.write('Warming course data...')
                warm_course_data()
                self.stdout.write(
                    self.style.SUCCESS('✓ Course cache warmed successfully')
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'Cache warm-up completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Cache warm-up failed: {str(e)}')
            )
            logger.error(f'Cache warm-up failed: {str(e)}', exc_info=True)