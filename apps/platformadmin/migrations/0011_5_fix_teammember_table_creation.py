# Generated migration to fix TeamMember table creation issue
# This migration manually creates the team member table that should have been created in 0010

from django.conf import settings
from django.db import migrations, models, connection
import django.db.models.deletion


def create_teammember_table(apps, schema_editor):
    """
    Manually create the TeamMember table if it doesn't exist
    This fixes the issue where the table wasn't created due to managed=False in migration 0010
    """
    with connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'platformadmin_teammember'
        """)
        
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            # Create the table manually
            cursor.execute("""
                CREATE TABLE platformadmin_teammember (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    designation VARCHAR(200) NOT NULL,
                    subject VARCHAR(200) NOT NULL DEFAULT '',
                    years_of_experience INT UNSIGNED NOT NULL DEFAULT 0,
                    photo VARCHAR(100) NOT NULL,
                    bio LONGTEXT NOT NULL,
                    email VARCHAR(254) NOT NULL DEFAULT '',
                    phone VARCHAR(20) NOT NULL DEFAULT '',
                    linkedin_url VARCHAR(200) NOT NULL DEFAULT '',
                    twitter_url VARCHAR(200) NOT NULL DEFAULT '',
                    facebook_url VARCHAR(200) NOT NULL DEFAULT '',
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    display_order INT UNSIGNED NOT NULL DEFAULT 0,
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                    created_by_id BIGINT NULL,
                    INDEX platformadm_is_acti_70c4f0_idx (is_active, display_order),
                    CONSTRAINT platformadmin_teammember_created_by_id_fk 
                        FOREIGN KEY (created_by_id) REFERENCES auth_user (id) ON DELETE SET NULL
                )
            """)


def reverse_create_teammember_table(apps, schema_editor):
    """
    Drop the TeamMember table if it was created by this migration
    """
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS platformadmin_teammember")


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0011_alter_teammember_options'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            create_teammember_table,
            reverse_create_teammember_table
        ),
    ]