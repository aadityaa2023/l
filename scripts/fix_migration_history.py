import os
import sys
import django

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leq.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DELETE FROM django_migrations WHERE app='platformadmin' AND name='0016_fix_teammember_table_creation'")
    print("Deleted 0016 from migration history")
