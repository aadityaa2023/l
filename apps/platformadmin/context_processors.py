from apps.platformadmin.models import FooterSettings

def footer_settings(request):
    """
    Context processor to make footer settings available to all templates.
    Checks if FooterSettings table exists to avoid migration issues.
    """
    try:
        settings = FooterSettings.get_settings()
        return {'footer_settings': settings}
    except Exception:
        # Return empty dict if table doesn't exist or other error
        return {}
