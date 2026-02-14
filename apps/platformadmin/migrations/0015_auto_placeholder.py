# Empty migration - placeholder for production database compatibility
# This migration exists to match database records from earlier deployments
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0014_add_updated_by_column'),
    ]

    operations = [
        # No operations - this is a placeholder migration
    ]
