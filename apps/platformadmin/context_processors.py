from apps.platformadmin.models import FooterSettings
import logging

logger = logging.getLogger(__name__)

def footer_settings(request):
    """
    Context processor to make footer settings available to all templates.
    Checks if FooterSettings table exists to avoid migration issues.
    """
    try:
        settings = FooterSettings.get_settings()
        return {'footer_settings': settings}
    except Exception as e:
        # Log the error for debugging in production
        logger.warning(f"Failed to load footer settings: {e}")
        # Return empty dict if table doesn't exist or other error
        return {'footer_settings': None}
