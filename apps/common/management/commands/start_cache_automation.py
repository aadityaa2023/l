"""
Management command to start cache automation daemon
Run as: python manage.py start_cache_automation
"""
from django.core.management.base import BaseCommand
from apps.common.cache_automation import start_cache_automation
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Start automated cache management and warming daemon'
    
    def handle(self, *args, **options):
        self.stdout.write("Starting cache automation daemon...")
        
        try:
            start_cache_automation()
            self.stdout.write(
                self.style.SUCCESS('Cache automation started successfully')
            )
            
            # Keep the process running
            import time
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\nCache automation interrupted')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error starting cache automation: {str(e)}')
            )
