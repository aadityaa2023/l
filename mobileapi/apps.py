from django.apps import AppConfig


class MobileApiConfig(AppConfig):
    """
    Mobile API Application Configuration
    Provides REST API endpoints for the React Native mobile app
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mobileapi'
    verbose_name = 'Mobile API'
    
    def ready(self):
        """
        Import signals and perform startup tasks
        """
        # Import signals if needed
        # import mobileapi.signals
        pass
