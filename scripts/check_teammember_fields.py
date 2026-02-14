import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leq.settings')
django.setup()

from apps.platformadmin.models import TeamMember

print([f.name for f in TeamMember._meta.get_fields()])
