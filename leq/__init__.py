# Patch mysql-connector-python 8.1.0 compatibility with Django 4.2
# This must run BEFORE any Django code imports the database backend
# Fixes: TypeError: DatabaseWrapper.display_name() takes 0 positional arguments but 1 was given

def _patch_mysql_connector():
    """Patch mysql.connector.django.base.DatabaseWrapper.display_name"""
    try:
        # Import and patch immediately
        from mysql.connector.django import base
        
        # Get the DatabaseWrapper class
        DatabaseWrapper = base.DatabaseWrapper
        
        # Only patch if display_name is not already a property
        if hasattr(DatabaseWrapper, 'display_name'):
            current = DatabaseWrapper.__dict__.get('display_name')
            if current is not None and not isinstance(current, property):
                # Replace with a property
                DatabaseWrapper.display_name = property(lambda self: 'MySQL')
                print("DEBUG: Patched mysql.connector DatabaseWrapper.display_name")
    except ImportError:
        # mysql-connector-python not installed
        pass
    except Exception as e:
        # Don't crash if patching fails
        print(f"WARNING: Could not patch mysql-connector: {e}")

# Apply patch immediately
_patch_mysql_connector()

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)