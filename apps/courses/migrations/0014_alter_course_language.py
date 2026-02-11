from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0013_remove_youtube_from_course'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='language',
            field=models.CharField(
                verbose_name='language',
                max_length=50,
                choices=[
                    ('Hindi', 'Hindi'),
                    ('English', 'English'),
                    ('Hindi + English', 'Hindi + English'),
                    ('Others', 'Others'),
                ],
                default='English',
            ),
        ),
    ]
