from django.apps import AppConfig


class PlatformadminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platformadmin'
    verbose_name = 'Platform Admin'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        # Import any signals here if needed in the future
        pass
    verbose_name = 'Platform Admin'
    
    def ready(self):
        """Import signals or other startup code here if needed"""
        pass

