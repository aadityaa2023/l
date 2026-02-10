"""
No-op migration to provide the missing migration node
Some production databases reference '0010_ensure_teammember_table' as a parent
for later merge migrations. Adding this minimal migration restores that node
so migration graph validation succeeds. It performs no schema changes.
"""
from django.db import migrations


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("platformadmin", "0009_recalculate_teacher_commissions"),
    ]

    operations = [
        migrations.RunPython(noop, noop),
    ]
