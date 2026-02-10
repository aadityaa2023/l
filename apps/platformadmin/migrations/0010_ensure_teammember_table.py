# Generated migration to ensure TeamMember table exists before later migrations
from django.conf import settings
from django.db import migrations, connection


def create_teammember_table(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name = 'platformadmin_teammember'
        """)
        exists = cursor.fetchone()[0] > 0
        if not exists:
            cursor.execute("""
                CREATE TABLE platformadmin_teammember (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    designation VARCHAR(200) NOT NULL,
                    subject VARCHAR(200) NOT NULL DEFAULT '',
                    years_of_experience INT UNSIGNED NOT NULL DEFAULT 0,
                    photo VARCHAR(200) NOT NULL,
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
                    INDEX platformadm_is_acti_70c4f0_idx (is_active, display_order)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            # Add FK if auth_user exists
            try:
                cursor.execute("""
                    ALTER TABLE platformadmin_teammember
                    ADD CONSTRAINT platformadmin_teammember_created_by_id_fk
                    FOREIGN KEY (created_by_id) REFERENCES auth_user (id) ON DELETE SET NULL
                """)
            except Exception:
                # If auth_user doesn't exist yet or FK fails, ignore; later migrations will handle
                pass


def noop_reverse(apps, schema_editor):
    # Do not drop the table on reverse to avoid data loss
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0009_recalculate_teacher_commissions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_teammember_table, noop_reverse),
    ]
