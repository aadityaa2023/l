# Merge migration - resolves two parallel development branches
# This migration exists to match database records from earlier deployments
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0014_add_updated_by_column'),
        ('platformadmin', '0016_fix_teammember_table_creation'),
    ]

    operations = [
        # No operations - this is a merge migration
    ]
