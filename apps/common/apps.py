from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    
    def ready(self):
        """Import signal handlers when the app is ready"""
        try:
            import apps.common.cache_signals  # noqa
        except ImportError:
            pass

