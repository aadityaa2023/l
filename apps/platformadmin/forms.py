"""
Forms for platformadmin dashboard
"""
from django import forms
from django.contrib.auth import get_user_model
from apps.courses.models import Course, Category
from apps.platformadmin.models import CourseApproval, PlatformSetting
from decimal import Decimal

User = get_user_model()


class UserManagementForm(forms.Form):
    """Form for managing user status"""
    
    ACTION_CHOICES = (
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('suspend', 'Suspend'),
        ('change_role', 'Change Role'),
        ('verify_teacher', 'Verify Teacher'),
    )
    
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    )
    
    action = forms.ChoiceField(choices=ACTION_CHOICES, required=True)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, max_length=500)
    new_role = forms.ChoiceField(choices=ROLE_CHOICES, required=False)


class BulkUserActionForm(forms.Form):
    """Form for bulk user actions"""
    
    ACTION_CHOICES = (
        ('activate', 'Activate Selected Users'),
        ('deactivate', 'Deactivate Selected Users'),
        ('verify_teachers', 'Verify Selected Teachers'),
        ('send_email', 'Send Email to Selected Users'),
    )
    
    user_ids = forms.CharField(widget=forms.HiddenInput(), required=True)
    action = forms.ChoiceField(choices=ACTION_CHOICES, required=True, widget=forms.Select(attrs={
        'class': 'form-control',
    }))
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False,
        max_length=500,
        label='Reason/Message'
    )


class RefundForm(forms.Form):
    """Form for processing refunds"""
    
    REASON_CHOICES = (
        ('not_satisfied', 'Customer Not Satisfied'),
        ('technical_issue', 'Technical Issue'),
        ('duplicate_payment', 'Duplicate Payment'),
        ('course_cancelled', 'Course Cancelled'),
        ('admin_discretion', 'Admin Discretion'),
        ('other', 'Other'),
    )
    
    refund_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave empty for full refund',
            'step': '0.01'
        }),
        label='Refund Amount (optional)'
    )
    refund_reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Refund Reason'
    )
    admin_notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        required=True,
        max_length=1000,
        label='Admin Notes'
    )
    confirm = forms.BooleanField(
        required=True,
        label='I confirm this refund is authorized'
    )


class BulkRefundForm(forms.Form):
    """Form for bulk refunds"""
    
    REASON_CHOICES = RefundForm.REASON_CHOICES
    
    payment_ids = forms.CharField(widget=forms.HiddenInput(), required=True)
    refund_reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Refund Reason'
    )
    admin_notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        required=True,
        max_length=1000,
        label='Admin Notes'
    )
    confirm = forms.BooleanField(
        required=True,
        label='I confirm these refunds are authorized'
    )


class CourseApprovalForm(forms.ModelForm):
    """Form for approving or rejecting courses"""
    
    class Meta:
        model = CourseApproval
        fields = ['status', 'review_comments', 'rejection_reason']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'review_comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add your review comments here...'
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Explain why the course is being rejected...'
            }),
        }


class CourseFilterForm(forms.Form):
    """Form for filtering courses"""
    
    STATUS_CHOICES = (
        ('', 'All Statuses'),
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    APPROVAL_STATUS_CHOICES = (
        ('', 'All Approval Status'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('revision_requested', 'Revision Requested'),
    )
    
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False, widget=forms.Select(attrs={
        'class': 'form-control form-control-sm',
    }))
    approval_status = forms.ChoiceField(choices=APPROVAL_STATUS_CHOICES, required=False, widget=forms.Select(attrs={
        'class': 'form-control form-control-sm',
    }))
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'form-control form-control-sm',
        })
    )
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-sm',
        'placeholder': 'Search by title or teacher...'
    }))


class PaymentFilterForm(forms.Form):
    """Form for filtering payments"""
    
    STATUS_CHOICES = (
        ('', 'All Statuses'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False, widget=forms.Select(attrs={
        'class': 'form-control form-control-sm',
    }))
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date'
        })
    )
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-sm',
        'placeholder': 'Search by email or order ID...'
    }))


class PlatformSettingsForm(forms.Form):
    """Form for managing platform settings"""
    
    enable_new_teachers = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    require_teacher_verification = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    require_course_approval = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


class CouponForm(forms.Form):
    """Form for creating/editing coupons"""
    
    DISCOUNT_TYPE_CHOICES = (
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )
    
    code = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'SUMMER2024',
            'style': 'text-transform: uppercase;'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2
        })
    )
    discount_type = forms.ChoiceField(
        choices=DISCOUNT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    discount_value = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    max_discount_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'For percentage coupons'
        })
    )
    min_purchase_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    valid_from = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    valid_until = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    max_uses = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave empty for unlimited'
        })
    )
    max_uses_per_user = forms.IntegerField(
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        })
    )


class CMSPageForm(forms.Form):
    """Form for CMS pages"""
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )
    
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Page Title'
        })
    )
    slug = forms.SlugField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'page-slug'
        })
    )
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10
        })
    )
    meta_title = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    meta_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3
        })
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_in_menu = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class FAQForm(forms.Form):
    """Form for FAQs"""
    
    CATEGORY_CHOICES = (
        ('general', 'General'),
        ('courses', 'Courses'),
        ('payments', 'Payments'),
        ('technical', 'Technical'),
        ('account', 'Account'),
    )
    
    question = forms.CharField(
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Question'
        })
    )
    answer = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4
        })
    )
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    order = forms.IntegerField(
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


class AnnouncementForm(forms.Form):
    """Form for announcements"""
    
    TYPE_CHOICES = (
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('danger', 'Danger'),
    )
    
    DISPLAY_CHOICES = (
        ('banner', 'Banner (top of page)'),
        ('popup', 'Popup'),
        ('dashboard', 'Dashboard only'),
    )
    
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Announcement Title'
        })
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4
        })
    )
    announcement_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    display_location = forms.ChoiceField(
        choices=DISPLAY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    target_all_users = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    target_students = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    target_teachers = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    end_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )


class BulkNotificationForm(forms.Form):
    """Form for sending bulk notifications"""
    
    TARGET_CHOICES = (
        ('all', 'All Users'),
        ('student', 'Students Only'),
        ('teacher', 'Teachers Only'),
    )
    
    target_role = forms.ChoiceField(
        choices=TARGET_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Target Audience'
    )
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Notification Title'
        })
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Notification message...'
        })
    )
    send_email = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Also send as email'
    )


class SendBulkNotificationForm(forms.Form):
    """Form for composing bulk notifications from platform admin."""

    TARGET_CHOICES = (
        ('all', 'All Users'),
        ('student', 'Students'),
        ('teacher', 'Teachers'),
        ('admin', 'Platform Admins'),
    )

    NOTIFICATION_TYPE_CHOICES = (
        ('announcement', 'Announcement'),
        ('reminder', 'Reminder'),
        ('promotion', 'Promotion'),
    )

    target_role = forms.ChoiceField(choices=TARGET_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    notification_type = forms.ChoiceField(choices=NOTIFICATION_TYPE_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    title = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter notification title'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Enter notification message'}))
    action_url = forms.URLField(required=False, widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com/action'}))
    send_email = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    send_push = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    scheduled_time = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}))



class PayoutApprovalForm(forms.Form):
    """Form for approving payouts"""
    
    transaction_reference = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Transaction/UTR number'
        })
    )
    admin_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any notes about this payout...'
        })
    )
    confirm = forms.BooleanField(
        required=True,
        label='I confirm the payment has been processed'
    )


class PayoutRejectionForm(forms.Form):
    """Form for rejecting payouts"""
    
    rejection_reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Explain why this payout is being rejected...'
        })
    )


class BannerForm(forms.Form):
    """Form for creating and editing banners"""
    
    BANNER_TYPE_CHOICES = (
        ('home', 'Home Page'),
        ('course', 'Course Page'),
        ('offer', 'Special Offer'),
    )
    
    title = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter banner title/headline'
        }),
        label='Title'
    )
    
    description = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter banner description/message'
        }),
        label='Description'
    )
    
    image = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label='Banner Image',
        help_text='Recommended size: 1920x600px'
    )
    
    button_text = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., "Enroll Now", "Learn More"'
        }),
        label='Button Text (Optional)'
    )
    
    button_link = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., /courses/python-101/ or https://example.com'
        }),
        label='Button Link (Optional)'
    )
    
    banner_type = forms.ChoiceField(
        choices=BANNER_TYPE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Banner Type',
        initial='home'
    )
    
    priority = forms.IntegerField(
        min_value=0,
        max_value=100,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0-100 (higher = more priority)'
        }),
        label='Priority',
        help_text='Higher priority banners appear first (0-100)'
    )
    
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Active'
    )
    
    start_date = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        label='Start Date',
        input_formats=['%Y-%m-%dT%H:%M']
    )
    
    end_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        label='End Date (Optional)',
        help_text='Leave blank for no expiration',
        input_formats=['%Y-%m-%dT%H:%M']
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and end_date <= start_date:
            raise forms.ValidationError('End date must be after start date.')
        
        return cleaned_data


class BannerFilterForm(forms.Form):
    """Form for filtering banners"""
    
    BANNER_TYPE_CHOICES = (
        ('', 'All Types'),
        ('home', 'Home Page'),
        ('course', 'Course Page'),
        ('offer', 'Special Offer'),
    )
    
    STATUS_CHOICES = (
        ('', 'All Status'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('scheduled', 'Scheduled'),
        ('expired', 'Expired'),
    )
    
    banner_type = forms.ChoiceField(
        choices=BANNER_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Type'
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Status'
    )
    
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search banners...'
        }),
        label='Search'
    )


class SendBulkNotificationForm(forms.Form):
    """Form for composing bulk notifications from platform admin."""

    TARGET_CHOICES = (
        ('all', 'All Users'),
        ('student', 'Students'),
        ('teacher', 'Teachers'),
        ('admin', 'Platform Admins'),
    )

    NOTIFICATION_TYPE_CHOICES = (
        ('announcement', 'Announcement'),
        ('reminder', 'Reminder'),
        ('promotion', 'Promotion'),
    )

    target_role = forms.ChoiceField(
        choices=TARGET_CHOICES, 
        required=True, 
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Target Audience'
    )
    notification_type = forms.ChoiceField(
        choices=NOTIFICATION_TYPE_CHOICES, 
        required=True, 
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Notification Type'
    )
    title = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter notification title'}),
        label='Title'
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Enter notification message'}),
        label='Message'
    )
    action_url = forms.URLField(
        required=False, 
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com/action'}),
        label='Action URL'
    )
    send_email = forms.BooleanField(
        required=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Send Email Notification'
    )
    send_push = forms.BooleanField(
        required=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Send Push Notification'
    )
    scheduled_time = forms.DateTimeField(
        required=False, 
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label='Schedule Time'
    )





class FooterSettingsForm(forms.Form):
    """Form for managing footer settings"""
    
    company_name = forms.CharField(
        max_length=200,
        initial='LeQ',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Company Name'
        }),
        label='Company Name'
    )
    
    company_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Short description about your company'
        }),
        label='Company Description'
    )
    
    contact_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'contact@example.com'
        }),
        label='Contact Email'
    )
    
    contact_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1 234 567 8900'
        }),
        label='Contact Phone'
    )
    
    contact_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Company address'
        }),
        label='Contact Address'
    )
    
    facebook_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://facebook.com/yourpage'
        }),
        label='Facebook URL'
    )
    
    twitter_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://twitter.com/yourhandle'
        }),
        label='Twitter URL'
    )
    
    instagram_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://instagram.com/yourhandle'
        }),
        label='Instagram URL'
    )
    
    linkedin_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://linkedin.com/company/yourcompany'
        }),
        label='LinkedIn URL'
    )
    
    youtube_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://youtube.com/c/yourchannel'
        }),
        label='YouTube URL'
    )
    
    github_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://github.com/yourorg'
        }),
        label='GitHub URL'
    )
    
    copyright_text = forms.CharField(
        max_length=200,
        initial='© 2024 LeQ. All rights reserved.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '© 2024 Your Company. All rights reserved.'
        }),
        label='Copyright Text'
    )
    
    privacy_policy_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': '/privacy-policy/'
        }),
        label='Privacy Policy URL'
    )
    
    terms_of_service_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': '/terms-of-service/'
        }),
        label='Terms of Service URL'
    )
    
    show_newsletter_signup = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Show Newsletter Signup'
    )
    
    newsletter_heading = forms.CharField(
        max_length=200,
        required=False,
        initial='Subscribe to our Newsletter',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Newsletter heading'
        }),
        label='Newsletter Heading'
    )
    
    newsletter_description = forms.CharField(
        required=False,
        initial='Get the latest updates and news.',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Newsletter description'
        }),
        label='Newsletter Description'
    )


class PageContentForm(forms.Form):
    """Form for managing page content"""
    
    PAGE_TYPE_CHOICES = (
        ('about_us', 'About Us'),
        ('contact_us', 'Contact Us'),
        ('privacy_policy', 'Privacy Policy'),
        ('terms_of_service', 'Terms of Service'),
        ('faq', 'FAQ'),
        ('custom', 'Custom Page'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )
    
    page_type = forms.ChoiceField(
        choices=PAGE_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Page Type'
    )
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Page Title'
        }),
        label='Page Title'
    )
    
    slug = forms.SlugField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'page-slug'
        }),
        label='Slug',
        help_text='URL-friendly version of the title'
    )
    
    hero_title = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Main heading at top of page'
        }),
        label='Hero Title'
    )
    
    hero_subtitle = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Subtitle or tagline'
        }),
        label='Hero Subtitle'
    )
    
    hero_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label='Hero Image'
    )
    
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Main page content (HTML supported)'
        }),
        label='Main Content'
    )
    
    meta_title = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'SEO meta title'
        }),
        label='Meta Title'
    )
    
    meta_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'SEO meta description'
        }),
        label='Meta Description'
    )
    
    meta_keywords = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'keyword1, keyword2, keyword3'
        }),
        label='Meta Keywords'
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Status'
    )
    
    show_in_footer = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Show in Footer'
    )
    
    show_in_header = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Show in Header Menu'
    )
    
    display_order = forms.IntegerField(
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Display order'
        }),
        label='Display Order'
    )


class TeamMemberForm(forms.Form):
    """Form for creating and editing team members"""
    
    name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full Name'
        }),
        label='Name'
    )
    
    designation = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Job Title or Role'
        }),
        label='Designation'
    )
    
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Area of Expertise'
        }),
        label='Subject/Expertise'
    )
    
    experience = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 5 years, 10+ years'
        }),
        label='Experience'
    )
    
    photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label='Photo',
        help_text='Recommended size: 400x400px'
    )
    
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Short biography or description'
        }),
        label='Biography'
    )
    
    linkedin_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://linkedin.com/in/username'
        }),
        label='LinkedIn URL'
    )
    
    twitter_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://twitter.com/username'
        }),
        label='Twitter URL'
    )
    
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Display on About Us Page'
    )
    
    display_order = forms.IntegerField(
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Display order (lower numbers first)'
        }),
        label='Display Order'
    )

