
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('platformadmin', '0009_recalculate_teacher_commissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='PageContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_type', models.CharField(choices=[('about_us', 'About Us'), ('contact_us', 'Contact Us'), ('privacy_policy', 'Privacy Policy'), ('terms_of_service', 'Terms of Service'), ('faq', 'FAQ'), ('custom', 'Custom Page')], max_length=50, unique=True, verbose_name='page type')),
                ('title', models.CharField(max_length=200, verbose_name='page title')),
                ('slug', models.SlugField(help_text='URL-friendly version of the title', unique=True, verbose_name='slug')),
                ('hero_title', models.CharField(blank=True, help_text='Main heading at top of page', max_length=200, verbose_name='hero title')),
                ('hero_subtitle', models.TextField(blank=True, help_text='Subtitle or tagline', verbose_name='hero subtitle')),
                ('hero_image', models.ImageField(blank=True, upload_to='page_content/', verbose_name='hero image')),
                ('content', models.TextField(help_text='Main page content (HTML supported)', verbose_name='main content')),
                ('additional_sections', models.JSONField(blank=True, default=dict, help_text='Additional content sections in JSON format', verbose_name='additional sections')),
                ('meta_title', models.CharField(blank=True, max_length=200, verbose_name='meta title')),
                ('meta_description', models.TextField(blank=True, verbose_name='meta description')),
                ('meta_keywords', models.CharField(blank=True, max_length=255, verbose_name='meta keywords')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('published', 'Published')], default='published', max_length=20, verbose_name='status')),
                ('show_in_footer', models.BooleanField(default=True, help_text='Display link in footer', verbose_name='show in footer')),
                ('show_in_header', models.BooleanField(default=False, help_text='Display link in header menu', verbose_name='show in header')),
                ('display_order', models.PositiveIntegerField(default=0, verbose_name='display order')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_page_contents', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_page_contents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'page content',
                'verbose_name_plural': 'page contents',
                'ordering': ['display_order', 'title'],
            },
        ),
        migrations.CreateModel(
            name='FooterSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(default='LeQ', max_length=200, verbose_name='company name')),
                ('company_description', models.TextField(blank=True, help_text='Short description in footer', verbose_name='company description')),
                ('contact_email', models.EmailField(blank=True, max_length=254, verbose_name='contact email')),
                ('contact_phone', models.CharField(blank=True, max_length=20, verbose_name='contact phone')),
                ('contact_address', models.TextField(blank=True, verbose_name='contact address')),
                ('facebook_url', models.URLField(blank=True, verbose_name='Facebook URL')),
                ('twitter_url', models.URLField(blank=True, verbose_name='Twitter URL')),
                ('instagram_url', models.URLField(blank=True, verbose_name='Instagram URL')),
                ('linkedin_url', models.URLField(blank=True, verbose_name='LinkedIn URL')),
                ('youtube_url', models.URLField(blank=True, verbose_name='YouTube URL')),
                ('github_url', models.URLField(blank=True, verbose_name='GitHub URL')),
                ('copyright_text', models.CharField(default='© 2024 LeQ. All rights reserved.', help_text='Copyright notice in footer', max_length=200, verbose_name='copyright text')),
                ('privacy_policy_url', models.URLField(blank=True, verbose_name='Privacy Policy URL')),
                ('terms_of_service_url', models.URLField(blank=True, verbose_name='Terms of Service URL')),
                ('show_newsletter_signup', models.BooleanField(default=True, verbose_name='show newsletter signup')),
                ('newsletter_heading', models.CharField(default='Subscribe to our Newsletter', max_length=200, verbose_name='newsletter heading')),
                ('newsletter_description', models.TextField(blank=True, default='Get the latest updates and news.', verbose_name='newsletter description')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='footer_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'footer settings',
                'verbose_name_plural': 'footer settings',
            },
        ),
    ]
