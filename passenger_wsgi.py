"""
Passenger WSGI entry point for shared hosting (Domainz)
This file is the entry point for Phusion Passenger to run the Django app.
"""
import sys
import os
from pathlib import Path

# Add the project directory to the Python path
INTERP = os.path.expanduser("~/virtualenvs/leq/bin/python")
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Set up the project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leq.settings')

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application

# Create the WSGI application
application = get_wsgi_application()
