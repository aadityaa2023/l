# Generated migration for commission and coupon assignment features - platformadmin models only

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0004_courseassignment'),
        ('payments', '0001_initial'),  # Needed for ForeignKey reference
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add commission_percentage to CourseAssignment
        migrations.AddField(
            model_name='courseassignment',
            name='commission_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=30.0,
                help_text='Platform commission percentage for this teacher on this course (default 30%)',
                max_digits=5,
                verbose_name='commission percentage'
            ),
        ),
        
        # Add assigned_coupons M2M to CourseAssignment
        migrations.AddField(
            model_name='courseassignment',
            name='assigned_coupons',
            field=models.ManyToManyField(
                blank=True,
                help_text='Coupons assigned to this teacher for this course',
                related_name='teacher_assignments',
                to='payments.coupon'
            ),
        ),
    ]
