"""
Platform Admin Dashboard Views
Custom admin panel for managing teachers, students, courses, and transactions
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from datetime import timedelta

from apps.platformadmin.decorators import platformadmin_required
from apps.platformadmin.forms import (
    UserManagementForm, CourseApprovalForm, CourseFilterForm,
    PaymentFilterForm, PlatformSettingsForm
)
from apps.platformadmin.utils import (
    DashboardStats, ReportGenerator, ActivityLog, get_context_data
)
from apps.platformadmin.models import AdminLog, CourseApproval, PlatformSetting
from apps.platformadmin.payment_handlers import RefundHandler, PaymentAnalytics
from apps.courses.models import Course, Category
from apps.payments.models import Payment, Refund

User = get_user_model()


@platformadmin_required
def dashboard(request):
    """Main admin dashboard"""
    context = get_context_data(request)
    
    # Additional dashboard metrics
    context['quick_stats'] = {
        'pending_approvals': CourseApproval.objects.filter(status='pending').count(),
        'unverified_teachers': User.objects.filter(
            role='teacher',
            teacher_profile__is_verified=False
        ).count(),
        'failed_transactions': Payment.objects.filter(status='failed').count(),
    }
    
    # Recent activities
    context['recent_approvals'] = CourseApproval.objects.select_related(
        'course', 'reviewed_by'
    ).filter(status__in=['pending']).order_by('-created_at')[:5]
    
    context['recent_payments'] = Payment.objects.select_related(
        'user', 'course'
    ).order_by('-created_at')[:10]
    
    return render(request, 'platformadmin/dashboard.html', context)


@platformadmin_required
def user_management(request):
    """Manage users (students and teachers)"""
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    users = User.objects.exclude(role='admin')
    
    # Filter by role
    if role_filter in ['student', 'teacher']:
        users = users.filter(role=role_filter)
    
    # Filter by status
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Search
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(users.order_by('-date_joined'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['users'] = page_obj.object_list
    context['role_filter'] = role_filter
    context['status_filter'] = status_filter
    context['search'] = search
    context['total_users'] = users.count()
    
    return render(request, 'platformadmin/user_management.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def user_detail(request, user_id):
    """View and manage individual user"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UserManagementForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            reason = form.cleaned_data['reason']
            
            old_values = {
                'is_active': user.is_active,
                'role': user.role,
            }
            
            # Handle different actions
            if action == 'activate':
                user.is_active = True
                messages.success(request, f"User {user.email} has been activated.")
            elif action == 'deactivate':
                user.is_active = False
                messages.success(request, f"User {user.email} has been deactivated.")
            elif action == 'suspend':
                user.is_active = False
                # Could add a suspend flag to the model
                messages.success(request, f"User {user.email} has been suspended.")
            elif action == 'change_role':
                new_role = form.cleaned_data.get('new_role')
                if new_role:
                    user.role = new_role
                    messages.success(request, f"User {user.email} role changed to {new_role}.")
            elif action == 'verify_teacher' and user.role == 'teacher':
                user.teacher_profile.is_verified = True
                user.teacher_profile.verification_date = timezone.now()
                user.teacher_profile.save()
                messages.success(request, f"Teacher {user.email} has been verified.")
            
            user.save()
            
            # Log the action
            new_values = {
                'is_active': user.is_active,
                'role': user.role,
            }
            ActivityLog.log_user_action(user, request.user, action, old_values, new_values, reason)
            
            return redirect('platformadmin:user_detail', user_id=user.id)
    else:
        form = UserManagementForm()
    
    context = get_context_data(request)
    context['user'] = user
    context['form'] = form
    
    # Additional user info
    if user.role == 'teacher':
        context['teacher_stats'] = {
            'total_courses': user.courses.count(),
            'published_courses': user.courses.filter(status='published').count(),
            'total_students': user.courses.aggregate(Sum('total_enrollments'))['total_enrollments__sum'] or 0,
        }
    elif user.role == 'student':
        context['student_stats'] = {
            'total_enrollments': user.enrollments.count() if hasattr(user, 'enrollments') else 0,
            'total_spent': Payment.objects.filter(user=user, status='completed').aggregate(Sum('amount'))['amount__sum'] or 0,
        }
    
    return render(request, 'platformadmin/user_detail.html', context)


@platformadmin_required
def course_management(request):
    """Manage courses and approvals"""
    form = CourseFilterForm(request.GET)
    courses = Course.objects.select_related('teacher', 'category')
    
    # Apply filters
    if form.is_valid():
        if form.cleaned_data.get('status'):
            courses = courses.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('category'):
            courses = courses.filter(category=form.cleaned_data['category'])
        if form.cleaned_data.get('search'):
            search = form.cleaned_data['search']
            courses = courses.filter(
                Q(title__icontains=search) |
                Q(teacher__email__icontains=search)
            )
        if form.cleaned_data.get('approval_status'):
            approval_status = form.cleaned_data['approval_status']
            courses = courses.filter(approval__status=approval_status)
    
    # Pagination
    paginator = Paginator(courses.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['courses'] = page_obj.object_list
    context['form'] = form
    context['total_courses'] = courses.count()
    
    return render(request, 'platformadmin/course_management.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def course_approval(request, course_id):
    """Approve or reject courses"""
    course = get_object_or_404(Course, id=course_id)
    approval, created = CourseApproval.objects.get_or_create(course=course)
    
    if request.method == 'POST':
        form = CourseApprovalForm(request.POST, instance=approval)
        if form.is_valid():
            old_status = approval.status
            approval = form.save(commit=False)
            approval.reviewed_by = request.user
            approval.reviewed_at = timezone.now()
            approval.save()
            
            # Log the action
            ActivityLog.log_course_action(
                course, request.user, 'approve' if approval.status == 'approved' else 'reject',
                {'status': old_status},
                {'status': approval.status},
                form.cleaned_data.get('review_comments', '')
            )
            
            messages.success(request, f"Course approval has been updated.")
            return redirect('platformadmin:course_management')
    else:
        form = CourseApprovalForm(instance=approval)
    
    context = get_context_data(request)
    context['course'] = course
    context['approval'] = approval
    context['form'] = form
    
    return render(request, 'platformadmin/course_approval.html', context)


@platformadmin_required
def payment_management(request):
    """Manage payments and transactions"""
    form = PaymentFilterForm(request.GET)
    payments = Payment.objects.select_related('user', 'course').order_by('-created_at')
    
    # Apply filters
    if form.is_valid():
        if form.cleaned_data.get('status'):
            payments = payments.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('date_from'):
            payments = payments.filter(created_at__date__gte=form.cleaned_data['date_from'])
        if form.cleaned_data.get('date_to'):
            payments = payments.filter(created_at__date__lte=form.cleaned_data['date_to'])
        if form.cleaned_data.get('search'):
            search = form.cleaned_data['search']
            payments = payments.filter(
                Q(user__email__icontains=search) |
                Q(razorpay_order_id__icontains=search)
            )
    
    # Pagination
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['payments'] = page_obj.object_list
    context['form'] = form
    
    # Additional stats
    context['payment_stats'] = {
        'total': payments.count(),
        'completed': payments.filter(status='completed').count(),
        'pending': payments.filter(status='pending').count(),
        'failed': payments.filter(status='failed').count(),
        'refunded': payments.filter(status='refunded').count(),
    }
    
    return render(request, 'platformadmin/payment_management.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def payment_detail(request, payment_id):
    """View payment details and handle refunds"""
    payment = get_object_or_404(Payment, id=payment_id)
    refund_handler = RefundHandler()
    
    # Check refund eligibility
    eligible, eligibility_reason = refund_handler.check_refund_eligibility(payment)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'refund':
            if not eligible:
                messages.error(request, f'Cannot process refund: {eligibility_reason}')
                return redirect('platformadmin:payment_detail', payment_id=payment.id)
            
            # Get refund details
            refund_amount = request.POST.get('refund_amount', '')
            refund_reason = request.POST.get('refund_reason', 'other')
            admin_notes = request.POST.get('admin_notes', '')
            
            # Determine if partial or full refund
            amount = None
            if refund_amount and refund_amount.strip():
                try:
                    amount = float(refund_amount)
                except ValueError:
                    messages.error(request, 'Invalid refund amount')
                    return redirect('platformadmin:payment_detail', payment_id=payment.id)
            
            # Process refund
            success, message, refund_obj = refund_handler.process_refund(
                payment=payment,
                admin_user=request.user,
                amount=amount,
                reason=refund_reason,
                admin_notes=admin_notes
            )
            
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
            
            return redirect('platformadmin:payment_management')
    
    context = get_context_data(request)
    context['payment'] = payment
    context['refund_eligible'] = eligible
    context['eligibility_reason'] = eligibility_reason
    
    # Add refund information if exists
    if hasattr(payment, 'refund'):
        context['refund'] = payment.refund
    
    return render(request, 'platformadmin/payment_detail.html', context)


@platformadmin_required
def analytics_report(request):
    """View analytics and reports"""
    report_type = request.GET.get('type', 'revenue')
    
    context = get_context_data(request)
    
    if report_type == 'revenue':
        context['report'] = ReportGenerator.get_revenue_report()
        context['title'] = 'Revenue Report'
    elif report_type == 'users':
        context['report'] = ReportGenerator.get_user_report()
        context['title'] = 'User Growth Report'
    elif report_type == 'courses':
        context['report'] = ReportGenerator.get_course_stats_report()
        context['title'] = 'Course Statistics Report'
    
    context['report_type'] = report_type
    
    return render(request, 'platformadmin/analytics_report.html', context)


@platformadmin_required
def activity_logs(request):
    """View admin activity logs"""
    logs = AdminLog.objects.select_related('admin').order_by('-created_at')
    
    # Filter by admin
    admin_id = request.GET.get('admin')
    if admin_id:
        logs = logs.filter(admin_id=admin_id)
    
    # Filter by action
    action = request.GET.get('action')
    if action:
        logs = logs.filter(action=action)
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['logs'] = page_obj.object_list
    context['admins'] = User.objects.filter(role='admin', is_staff=True)
    
    return render(request, 'platformadmin/activity_logs.html', context)


@platformadmin_required
def platform_settings(request):
    """Manage platform settings"""
    if request.method == 'POST':
        form = PlatformSettingsForm(request.POST)
        if form.is_valid():
            for key, value in form.cleaned_data.items():
                setting, created = PlatformSetting.objects.get_or_create(key=key)
                setting.value = str(value)
                setting.save()
            
            messages.success(request, "Settings updated successfully.")
            return redirect('platformadmin:platform_settings')
    else:
        # Load current settings
        settings_dict = {}
        for setting in PlatformSetting.objects.all():
            settings_dict[setting.key] = setting.value
        
        form = PlatformSettingsForm(initial=settings_dict)
    
    context = get_context_data(request)
    context['form'] = form
    context['settings'] = PlatformSetting.objects.all()
    
    return render(request, 'platformadmin/platform_settings.html', context)


@platformadmin_required
def teacher_verification(request):
    """Manage teacher verification"""
    teachers = User.objects.filter(role='teacher').select_related('teacher_profile')
    
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    if status_filter == 'verified':
        teachers = teachers.filter(teacher_profile__is_verified=True)
    elif status_filter == 'unverified':
        teachers = teachers.filter(teacher_profile__is_verified=False)
    
    if search:
        teachers = teachers.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(teachers.order_by('-date_joined'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['teachers'] = page_obj.object_list
    context['status_filter'] = status_filter
    context['search'] = search
    
    return render(request, 'platformadmin/teacher_verification.html', context)


# Email Preview Views
@platformadmin_required
def email_templates_list(request):
    """List all available email templates for preview"""
    import os
    from django.conf import settings
    
    # Get available email preview templates
    email_preview_dir = os.path.join(settings.BASE_DIR, 'templates', 'platformadmin', 'email_previews')
    email_templates = []
    
    if os.path.exists(email_preview_dir):
        for filename in os.listdir(email_preview_dir):
            if filename.endswith('.html'):
                template_name = filename.replace('.html', '')
                email_templates.append({
                    'template_name': template_name,
                    'name': template_name.replace('_', ' ').title(),
                    'subject': f'{template_name.replace("_", " ").title()} Email',
                    'updated_at': timezone.now(),
                })
    
    context = get_context_data(request)
    context['email_templates'] = email_templates
    return render(request, 'platformadmin/email_templates_list.html', context)


@platformadmin_required
def email_preview(request, template_name):
    """Preview email templates within platformadmin UI"""
    from decimal import Decimal
    from datetime import datetime, timedelta
    
    # Sample data for email previews
    sample_user = User.objects.filter(role='student').first() or User(
        email='sample@example.com',
        first_name='John',
        last_name='Doe',
        role='student'
    )
    
    sample_course = Course.objects.first() or type('Course', (), {
        'title': 'Sample Course',
        'description': 'Sample course description',
        'price': Decimal('999.00')
    })()
    
    sample_payment = type('Payment', (), {
        'amount': Decimal('999.00'),
        'transaction_id': 'TXN123456',
        'created_at': datetime.now()
    })()
    
    sample_refund = type('Refund', (), {
        'amount': Decimal('999.00'),
        'refund_id': 'RFN123456',
        'status': 'processed',
        'processed_at': datetime.now()
    })()
    
    context = {
        'sample_user': sample_user,
        'sample_course': sample_course,
        'sample_payment': sample_payment,
        'sample_refund': sample_refund,
        'sample_reason': 'This is a sample reason for the action taken.',
        'sample_duration': '7 days',
        'sample_old_role': 'Student',
        'sample_new_role': 'Platform Admin',
        'sample_subject': 'Important Platform Announcement',
        'sample_message': 'This is a sample bulk message sent to all users.',
        'teacher': sample_user,
        'user': sample_user,
        'course': sample_course,
        'payment': sample_payment,
        'refund': sample_refund,
        'reason': 'This is a sample reason for the action taken.',
        'duration': '7 days',
        'old_role': 'Student',
        'new_role': 'Platform Admin',
        'subject': 'Important Platform Announcement',
        'message': 'This is a sample bulk message sent to all users.',
    }
    
    template_path = f'platformadmin/email_previews/{template_name}.html'
    return render(request, template_path, context)


# ============================================================================
# BANNER MANAGEMENT VIEWS
# ============================================================================

@platformadmin_required
def banner_list(request):
    """List and manage all banners"""
    from apps.common.models import Banner
    from apps.platformadmin.forms import BannerFilterForm
    
    # Apply filters
    banner_type = request.GET.get('banner_type', '')
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    banners = Banner.objects.select_related('created_by').all()
    
    # Filter by type
    if banner_type:
        banners = banners.filter(banner_type=banner_type)
    
    # Filter by status
    now = timezone.now()
    if status == 'active':
        banners = banners.filter(
            is_active=True,
            start_date__lte=now,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
    elif status == 'inactive':
        banners = banners.filter(is_active=False)
    elif status == 'scheduled':
        banners = banners.filter(is_active=True, start_date__gt=now)
    elif status == 'expired':
        banners = banners.filter(is_active=True, end_date__lt=now)
    
    # Search
    if search:
        banners = banners.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(banners.order_by('-priority', '-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['banners'] = page_obj.object_list
    context['filter_form'] = BannerFilterForm(request.GET)
    context['total_banners'] = banners.count()
    context['now'] = now
    
    return render(request, 'platformadmin/banner_list.html', context)


@platformadmin_required
def banner_create(request):
    """Create a new banner"""
    from apps.common.models import Banner
    from apps.platformadmin.forms import BannerForm
    from apps.platformadmin.models import AdminLog
    
    if request.method == 'POST':
        form = BannerForm(request.POST, request.FILES)
        if form.is_valid():
            banner = Banner.objects.create(
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                image=form.cleaned_data['image'],
                button_text=form.cleaned_data.get('button_text', ''),
                button_link=form.cleaned_data.get('button_link', ''),
                banner_type=form.cleaned_data['banner_type'],
                priority=form.cleaned_data['priority'],
                is_active=form.cleaned_data.get('is_active', True),
                start_date=form.cleaned_data['start_date'],
                end_date=form.cleaned_data.get('end_date'),
                created_by=request.user
            )

            # Log the action with structured old/new values
            new_vals = {
                'title': banner.title,
                'description': banner.description,
                'banner_type': banner.banner_type,
                'priority': banner.priority,
                'is_active': banner.is_active,
            }
            AdminLog.objects.create(
                admin=request.user,
                action='create',
                content_type='Banner',
                object_id=str(banner.id),
                object_repr=banner.title,
                old_values={},
                new_values=new_vals,
            )
            
            messages.success(request, f'Banner "{banner.title}" created successfully!')
            return redirect('platformadmin:banner_list')
    else:
        # Set default start_date to now
        initial_data = {'start_date': timezone.now()}
        form = BannerForm(initial=initial_data)
    
    context = get_context_data(request)
    context['form'] = form
    context['form_title'] = 'Create New Banner'
    
    return render(request, 'platformadmin/banner_form.html', context)


@platformadmin_required
def banner_edit(request, banner_id):
    """Edit an existing banner"""
    from apps.common.models import Banner
    from apps.platformadmin.forms import BannerForm
    from apps.platformadmin.models import AdminLog
    
    banner = get_object_or_404(Banner, id=banner_id)
    
    if request.method == 'POST':
        form = BannerForm(request.POST, request.FILES)
        if form.is_valid():
            # Capture old values for audit
            old_vals = {
                'title': banner.title,
                'description': banner.description,
                'banner_type': banner.banner_type,
                'priority': banner.priority,
                'is_active': banner.is_active,
            }

            # Update banner fields
            banner.title = form.cleaned_data['title']
            banner.description = form.cleaned_data['description']
            if 'image' in request.FILES:
                banner.image = form.cleaned_data['image']
            banner.button_text = form.cleaned_data.get('button_text', '')
            banner.button_link = form.cleaned_data.get('button_link', '')
            banner.banner_type = form.cleaned_data['banner_type']
            banner.priority = form.cleaned_data['priority']
            banner.is_active = form.cleaned_data.get('is_active', True)
            banner.start_date = form.cleaned_data['start_date']
            banner.end_date = form.cleaned_data.get('end_date')
            banner.save()

            # Log the action with before/after
            new_vals = {
                'title': banner.title,
                'description': banner.description,
                'banner_type': banner.banner_type,
                'priority': banner.priority,
                'is_active': banner.is_active,
            }
            AdminLog.objects.create(
                admin=request.user,
                action='update',
                content_type='Banner',
                object_id=str(banner.id),
                object_repr=banner.title,
                old_values=old_vals,
                new_values=new_vals,
            )
            
            messages.success(request, f'Banner "{banner.title}" updated successfully!')
            return redirect('platformadmin:banner_list')
    else:
        # Populate form with existing data
        initial_data = {
            'title': banner.title,
            'description': banner.description,
            'button_text': banner.button_text,
            'button_link': banner.button_link,
            'banner_type': banner.banner_type,
            'priority': banner.priority,
            'is_active': banner.is_active,
            'start_date': banner.start_date,
            'end_date': banner.end_date,
        }
        form = BannerForm(initial=initial_data)
    
    context = get_context_data(request)
    context['form'] = form
    context['banner'] = banner
    context['form_title'] = f'Edit Banner: {banner.title}'
    
    return render(request, 'platformadmin/banner_form.html', context)


@platformadmin_required
def banner_delete(request, banner_id):
    """Delete a banner"""
    from apps.common.models import Banner
    from apps.platformadmin.models import AdminLog
    
    banner = get_object_or_404(Banner, id=banner_id)
    
    if request.method == 'POST':
        banner_title = banner.title
        # Capture old values before delete for audit
        old_vals = {
            'title': banner.title,
            'description': banner.description,
            'banner_type': banner.banner_type,
            'priority': banner.priority,
            'is_active': banner.is_active,
        }
        banner.delete()

        # Log the action
        AdminLog.objects.create(
            admin=request.user,
            action='delete',
            content_type='Banner',
            object_id=str(banner_id),
            object_repr=banner_title,
            old_values=old_vals,
            new_values={},
        )
        
        messages.success(request, f'Banner "{banner_title}" deleted successfully!')
        return redirect('platformadmin:banner_list')
    
    context = get_context_data(request)
    context['banner'] = banner
    
    return render(request, 'platformadmin/banner_confirm_delete.html', context)


@platformadmin_required
@require_http_methods(["POST"])
def banner_toggle_status(request, banner_id):
    """Toggle banner active status via AJAX"""
    from apps.common.models import Banner
    from apps.platformadmin.models import AdminLog
    
    banner = get_object_or_404(Banner, id=banner_id)
    prev_active = banner.is_active
    banner.is_active = not prev_active
    banner.save()

    # Log the action
    AdminLog.objects.create(
        admin=request.user,
        action='update',
        content_type='Banner',
        object_id=str(banner.id),
        object_repr=banner.title,
        old_values={'is_active': prev_active},
        new_values={'is_active': banner.is_active},
    )
    
    return JsonResponse({
        'success': True,
        'is_active': banner.is_active,
        'message': f'Banner {"activated" if banner.is_active else "deactivated"} successfully!'
    })


