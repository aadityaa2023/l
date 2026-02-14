"""Ensure 'experience' column exists on platformadmin_teammember.

This migration is database-agnostic and works with MySQL, PostgreSQL, SQLite.
Uses Django's schema introspection to safely add the column if missing.
"""
from django.db import migrations, models


def add_experience_if_missing(apps, schema_editor):
    """Add experience field if it doesn't exist (database-agnostic)"""
    db_alias = schema_editor.connection.alias
    table_name = 'platformadmin_teammember'
    column_name = 'experience'
    
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
        field = models.CharField(max_length=100, null=True, blank=True)
        field.set_attributes_from_name(column_name)
        schema_editor.add_field(TeamMember, field)


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0012_teammember'),
    ]

    operations = [
        migrations.RunPython(add_experience_if_missing, migrations.RunPython.noop),
    ]
