# Generated migration for coupon commission features - payments models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_payment_encrypted_bank_name_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add creator_type to Coupon
        migrations.AddField(
            model_name='coupon',
            name='creator_type',
            field=models.CharField(
                choices=[('platform_admin', 'Platform Admin'), ('teacher', 'Teacher')],
                default='platform_admin',
                help_text='Who created/owns this coupon',
                max_length=20,
                verbose_name='creator type'
            ),
        ),
        
        # Add assigned_to_teacher to Coupon
        migrations.AddField(
            model_name='coupon',
            name='assigned_to_teacher',
            field=models.ForeignKey(
                blank=True,
                help_text='If this is a teacher coupon, which teacher it belongs to',
                limit_choices_to={'role': 'teacher'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_teacher_coupons',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        
        # Add extra_commission_earned to CouponUsage
        migrations.AddField(
            model_name='couponusage',
            name='extra_commission_earned',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Extra commission earned from using this coupon (equals coupon discount %)',
                max_digits=10,
                verbose_name='extra commission earned'
            ),
        ),
        
        # Add commission_recipient to CouponUsage
        migrations.AddField(
            model_name='couponusage',
            name='commission_recipient',
            field=models.ForeignKey(
                blank=True,
                help_text='Who receives the extra commission (Platform Admin or Teacher)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='commission_from_coupons',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
