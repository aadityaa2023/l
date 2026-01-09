"""Passenger WSGI entry point for Django on shared hosting.

This file is executed by Phusion Passenger. It sets up the Python path,
activates the virtualenv, and exposes the WSGI application as `application`.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Ensure project root is on sys.path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Activate the virtualenv (adjust path if your host uses a different layout)
VENV_ACTIVATE = Path.home() / "virtualenv" / "l" / "bin" / "activate_this.py"
try:
    with open(VENV_ACTIVATE) as f:
        code = compile(f.read(), str(VENV_ACTIVATE), 'exec')
        exec(code, {'__file__': str(VENV_ACTIVATE)})
except FileNotFoundError:
    # Fallback: try alternate common location used by cPanel Python selector
    alt = Path.home() / "virtualenv" / "l" / "3.10" / "bin" / "activate_this.py"
    try:
        with open(alt) as f:
            code = compile(f.read(), str(alt), 'exec')
            exec(code, {'__file__': str(alt)})
    except FileNotFoundError:
        # If activation fails, continue with system Python (not ideal but avoids crash)
        pass

# Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leq.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
