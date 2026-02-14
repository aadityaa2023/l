"""Add missing updated_by_id column to platformadmin_teammember if absent.

Database-agnostic migration compatible with MySQL, PostgreSQL, SQLite.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def add_updated_by_if_missing(apps, schema_editor):
    """Add updated_by field if it doesn't exist (database-agnostic)"""
    db_alias = schema_editor.connection.alias
    table_name = 'platformadmin_teammember'
    column_name = 'updated_by_id'
    
    # Check if table exists
    if table_name not in schema_editor.connection.introspection.table_names():
        return
    
    # Get existing columns
    with schema_editor.connection.cursor() as cursor:
        existing_columns = [col.name for col in 
                          schema_editor.connection.introspection.get_table_description(
                              cursor, table_name)]
    
    # Add column if missing
    if column_name not in existing_columns:
        TeamMember = apps.get_model('platformadmin', 'TeamMember')
        field = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            related_name='updated_team_members'
        )
        field.set_attributes_from_name('updated_by')
        schema_editor.add_field(TeamMember, field)


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0013_fix_teammember_experience'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(add_updated_by_if_missing, migrations.RunPython.noop),
    ]
