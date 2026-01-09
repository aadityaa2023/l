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

# Load production environment variables from .env.production
ENV_FILE = BASE_DIR / '.env.production'
if ENV_FILE.exists():
    print(f"Loading environment from {ENV_FILE}")
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
else:
    print(f"Warning: {ENV_FILE} not found, using default settings")

# Activate the virtualenv - try multiple common paths for Domainz/cPanel
venv_paths = [
    Path.home() / "virtualenv" / "leqaudio_com" / "3.10" / "bin" / "activate_this.py",
    Path.home() / "virtualenv" / "leqaudio.com" / "3.10" / "bin" / "activate_this.py",
    Path.home() / "virtualenv" / "l" / "3.10" / "bin" / "activate_this.py",
    Path.home() / "virtualenv" / "leqaudio_com" / "bin" / "activate_this.py",
    Path.home() / ".virtualenvs" / "leq" / "bin" / "activate_this.py",
    Path.home() / "virtualenv" / "leq" / "bin" / "activate_this.py",
]

venv_activated = False
for venv_path in venv_paths:
    try:
        if venv_path.exists():
            print(f"Activating virtualenv: {venv_path}")
            with open(venv_path) as f:
                code = compile(f.read(), str(venv_path), 'exec')
                exec(code, {'__file__': str(venv_path)})
            venv_activated = True
            break
    except Exception as e:
        print(f"Failed to activate {venv_path}: {e}")
        continue

if not venv_activated:
    print("Warning: No virtualenv activated, using system Python")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")

# Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leq.settings")

# Import Django WSGI application
try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    print("Django WSGI application loaded successfully")
except Exception as e:
    print(f"ERROR loading Django WSGI application: {e}")
    import traceback
    traceback.print_exc()
    # Re-raise to let Passenger show the error
    raise
