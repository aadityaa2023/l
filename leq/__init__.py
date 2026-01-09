# Patch mysql-connector-python 8.1.0 compatibility issue with Django 4.2
# Must be done BEFORE Django loads any database connections
# Fixes: TypeError: DatabaseWrapper.display_name() takes 0 positional arguments but 1 was given

# Monkey-patch the mysql.connector module at import time
import sys

class MySQLConnectorPatcher:
    """Import hook to patch mysql.connector.django when it's imported"""
    
    def find_module(self, fullname, path=None):
        if fullname == 'mysql.connector.django.base':
            return self
        return None
    
    def load_module(self, fullname):
        if fullname in sys.modules:
            return sys.modules[fullname]
        
        # Import the module normally
        import importlib
        module = importlib.import_module(fullname)
        
        # Patch the DatabaseWrapper class
        try:
            DatabaseWrapper = module.DatabaseWrapper
            
            # Check if display_name is a method that needs patching
            if hasattr(DatabaseWrapper, 'display_name'):
                attr = DatabaseWrapper.__dict__.get('display_name')
                
                # If it's a function (not already a property), make it a property
                if callable(attr) and not isinstance(attr, property):
                    # Create a new property that returns 'MySQL'
                    DatabaseWrapper.display_name = property(lambda self: 'MySQL')
                    print("DEBUG: Patched mysql.connector DatabaseWrapper.display_name to be a property")
        except Exception as e:
            print(f"WARNING: Failed to patch mysql.connector: {e}")
        
        return module

# Install the import hook
sys.meta_path.insert(0, MySQLConnectorPatcher())

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)