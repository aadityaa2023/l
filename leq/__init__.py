# Patch mysql-connector-python 8.1.0 compatibility issue with Django 4.2
# Must be done BEFORE Django loads any database connections
# Fixes: TypeError: DatabaseWrapper.display_name() takes 0 positional arguments but 1 was given
import sys

def patch_mysql_connector():
    """Patch mysql.connector.django to work with Django 4.2+"""
    try:
        # Only patch if mysql.connector is available
        import mysql.connector.django.base
        
        # Get the DatabaseWrapper class
        DatabaseWrapper = mysql.connector.django.base.DatabaseWrapper
        
        # Check if display_name exists and needs patching
        if hasattr(DatabaseWrapper, 'display_name'):
            display_name_attr = getattr(DatabaseWrapper, 'display_name')
            
            # If it's a method (callable but not a property), patch it
            if callable(display_name_attr) and not isinstance(display_name_attr, property):
                # Replace the method with a property that returns 'MySQL'
                DatabaseWrapper.display_name = property(lambda self: 'MySQL')
                print("DEBUG: Patched mysql.connector.django.base.DatabaseWrapper.display_name")
    except ImportError:
        # mysql-connector-python not installed, no patch needed
        pass
    except Exception as e:
        # Don't fail if patching fails, just warn
        print(f"WARNING: Could not patch mysql-connector-python: {e}")

# Apply the patch immediately
patch_mysql_connector()

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)