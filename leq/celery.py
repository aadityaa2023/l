import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leq.settings')

app = Celery('leq')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Periodic Tasks Configuration
app.conf.beat_schedule = {
    'calculate-daily-analytics': {
        'task': 'apps.analytics.tasks.calculate_daily_analytics',
        'schedule': crontab(hour=1, minute=0),  # Run daily at 1 AM
    },
    'update-course-analytics': {
        'task': 'apps.analytics.tasks.update_course_analytics',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
    },
    'update-teacher-analytics': {
        'task': 'apps.analytics.tasks.update_teacher_analytics',
        'schedule': crontab(hour=3, minute=0),  # Run daily at 3 AM
    },
    'send-pending-notifications': {
        'task': 'apps.notifications.tasks.send_pending_notifications',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'cleanup-old-sessions': {
        'task': 'apps.analytics.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=0, minute=0, day_of_week=0),  # Weekly on Sunday
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
