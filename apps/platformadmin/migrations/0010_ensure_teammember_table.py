"""
Empty migration created to satisfy a missing dependency reference.
This migration intentionally has no operations; it ensures the
migration graph contains the node '0010_ensure_teammember_table'.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0009_recalculate_teacher_commissions'),
    ]

    operations = [
    ]
