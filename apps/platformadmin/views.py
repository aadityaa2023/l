from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

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
from apps.courses.models import Course, Category, Module
from apps.payments.models import Payment, Refund

User = get_user_model()


@platformadmin_required
def dashboard(request):
    """Main admin dashboard"""
    from apps.platformadmin.utils import get_platform_earnings
    
    context = get_context_data(request)
    
    # Get platform earnings
    earnings = get_platform_earnings()
    
    # Additional dashboard metrics
    context['quick_stats'] = {
        'pending_approvals': CourseApproval.objects.filter(status='pending').count(),
        'unverified_teachers': User.objects.filter(
            role='teacher',
            teacher_profile__is_verified=False
        ).count(),
        'failed_transactions': Payment.objects.filter(status='failed').count(),
    }
    
    # Platform earnings stats
    context['platform_earnings'] = earnings
    
    return render(request, 'platformadmin/dashboard.html', context)


@platformadmin_required
def user_management(request):
    """Manage users (students and teachers)"""
    from django.http import JsonResponse
    
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    users = User.objects.exclude(role='admin')
    
    # Filter by role
    if role_filter in ['student', 'teacher']:
        users = users.filter(role=role_filter)
    else:
        # Default to students for free user assignment
        users = users.filter(role='student')
    
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
    
    # Check if JSON response is requested
    if request.GET.get('json') == '1':
        from apps.platformadmin.models import FreeUser
        users_list = []
        for user in users[:10]:  # Limit to 10 results
            is_free_user = FreeUser.objects.filter(user=user, is_active=True).exists()
            users_list.append({
                'id': user.id,
                'name': user.get_full_name() or user.email,
                'email': user.email,
                'is_free_user': is_free_user,
            })
        return JsonResponse({'users': users_list})
    
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
    approval, _ = CourseApproval.objects.get_or_create(course=course)
    
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
            
            messages.success(request, "Course approval has been updated.")
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
                success, message, _ = refund_handler.process_refund(
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
    """View analytics and reports with enhanced data visualization"""
    from apps.courses.models import Enrollment
    import json
    from decimal import Decimal
    from datetime import datetime, timedelta
    
    report_type = request.GET.get('type', 'overview')
    days = int(request.GET.get('days', 30))
    
    context = get_context_data(request)
    
    # Helper function to convert Decimal to float
    def decimal_to_float(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [decimal_to_float(item) for item in obj]
        return obj
    
    # Helper function to fill missing dates
    def fill_date_range(data_dict, start_date, end_date):
        """Fill missing dates with 0 values"""
        filled_data = {}
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            filled_data[date_str] = data_dict.get(date_str, 0)
            current_date += timedelta(days=1)
        return filled_data
    
    # Overview with all key metrics
    if report_type == 'overview':
        revenue_report = ReportGenerator.get_revenue_report(days=days)
        user_report = ReportGenerator.get_user_report(days=days)
        course_report = ReportGenerator.get_course_stats_report()
        
        # Enrollment trends
        start_date = (timezone.now() - timedelta(days=days)).date()
        end_date = timezone.now().date()
        
        enrollments = Enrollment.objects.filter(
            enrolled_at__gte=timezone.now() - timedelta(days=days)
        )
        daily_enrollments = {}
        for enrollment in enrollments:
            date_str = enrollment.enrolled_at.date().isoformat()
            daily_enrollments[date_str] = daily_enrollments.get(date_str, 0) + 1
        
        # Fill missing dates
        daily_enrollments_filled = fill_date_range(daily_enrollments, start_date, end_date)
        revenue_filled = fill_date_range(
            {k: float(v) for k, v in revenue_report['daily_revenue'].items()},
            start_date,
            end_date
        )
        
        # Prepare chart data
        chart_data = {
            'revenue': {
                'labels': sorted(revenue_filled.keys()),
                'data': [revenue_filled[k] for k in sorted(revenue_filled.keys())]
            },
            'enrollments': {
                'labels': sorted(daily_enrollments_filled.keys()),
                'data': [daily_enrollments_filled[k] for k in sorted(daily_enrollments_filled.keys())]
            },
            'users': {
                'teachers': user_report.get('new_teachers', 0),
                'students': user_report.get('new_students', 0)
            },
            'courses': {
                'published': course_report['by_status'].get('published', 0),
                'draft': course_report['by_status'].get('draft', 0),
                'archived': course_report['by_status'].get('archived', 0)
            }
        }
        
        context.update({
            'title': 'Analytics Overview',
            'revenue_report': decimal_to_float(revenue_report),
            'user_report': decimal_to_float(user_report),
            'course_report': decimal_to_float(course_report),
            'total_enrollments': enrollments.count(),
            'chart_data': json.dumps(chart_data),
        })
        
    elif report_type == 'revenue':
        report = ReportGenerator.get_revenue_report(days=days)
        start_date = (timezone.now() - timedelta(days=days)).date()
        end_date = timezone.now().date()
        
        revenue_filled = fill_date_range(
            {k: float(v) for k, v in report['daily_revenue'].items()},
            start_date,
            end_date
        )
        
        chart_data = {
            'labels': sorted(revenue_filled.keys()),
            'data': [revenue_filled[k] for k in sorted(revenue_filled.keys())]
        }
        
        context['report'] = decimal_to_float(report)
        context['chart_data'] = json.dumps(chart_data)
        context['title'] = 'Revenue Analytics'
        
    elif report_type == 'users':
        report = ReportGenerator.get_user_report(days=days)
        start_date = (timezone.now() - timedelta(days=days)).date()
        end_date = timezone.now().date()
        
        # Prepare user growth data
        all_dates = []
        current_date = start_date
        while current_date <= end_date:
            all_dates.append(current_date.isoformat())
            current_date += timedelta(days=1)
        
        teachers_data = []
        students_data = []
        for date_str in all_dates:
            user_data = report['daily_users'].get(date_str, {'teachers': 0, 'students': 0})
            teachers_data.append(user_data.get('teachers', 0))
            students_data.append(user_data.get('students', 0))
        
        chart_data = {
            'labels': all_dates,
            'teachers': teachers_data,
            'students': students_data
        }
        
        context['report'] = decimal_to_float(report)
        context['chart_data'] = json.dumps(chart_data)
        context['title'] = 'User Growth Analytics'
        
    elif report_type == 'courses':
        report = ReportGenerator.get_course_stats_report()
        
        # Prepare teacher and category data
        teacher_labels = []
        teacher_counts = []
        for teacher in report['by_teacher'][:10]:
            first_name = teacher.get('teacher__first_name', '') or ''
            last_name = teacher.get('teacher__last_name', '') or ''
            name = f"{first_name} {last_name}".strip()
            if not name:
                name = (teacher.get('teacher__email', '') or 'Unknown').split('@')[0]
            teacher_labels.append(name)
            teacher_counts.append(teacher.get('count', 0))
        
        category_labels = []
        category_counts = []
        for cat in report['category_distribution'][:6]:
            category_labels.append(cat.get('category__name') or 'Uncategorized')
            category_counts.append(cat.get('count', 0))
        
        chart_data = {
            'teachers': {
                'labels': teacher_labels,
                'data': teacher_counts
            },
            'categories': {
                'labels': category_labels,
                'data': category_counts
            }
        }
        
        context['report'] = decimal_to_float(report)
        context['chart_data'] = json.dumps(chart_data)
        context['title'] = 'Course Analytics'
    
    context['report_type'] = report_type
    context['days'] = days
    
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
                setting, _ = PlatformSetting.objects.get_or_create(key=key)
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


# ==================== COURSE MANAGEMENT (PLATFORMADMIN CREATES & ASSIGNS) ====================

@platformadmin_required
def admin_course_create(request):
    """Platform admin creates a new course"""
    if request.method == 'POST':
        try:
            # Create course
            course = Course.objects.create(
                created_by=request.user,
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                short_description=request.POST.get('short_description', ''),
                
                # Handle category selection - subcategory takes precedence over main category
                category_id=(request.POST.get('category') or request.POST.get('main_category')) if (request.POST.get('category') or request.POST.get('main_category')) else None,
                
                level=request.POST.get('level', 'beginner'),
                language=request.POST.get('language', 'English'),
                price=request.POST.get('price', 0),
                discount_price=request.POST.get('discount_price') if request.POST.get('discount_price') else None,
                is_free=request.POST.get('is_free') == 'on',
                status='draft',
                allow_download=request.POST.get('allow_download') == 'on',
            )
            
            if 'thumbnail' in request.FILES:
                course.thumbnail = request.FILES['thumbnail']
                course.save()
            
            # Log the action
            AdminLog.objects.create(
                admin=request.user,
                action='create',
                content_type='Course',
                object_id=str(course.id),
                object_repr=course.title,
                new_values={
                    'title': course.title,
                    'status': course.status,
                    'price': str(course.price),
                }
            )
            
            messages.success(request, f'Course "{course.title}" created successfully!')
            return redirect('platformadmin:admin_course_edit', course_id=course.id)
        except Exception as e:
            messages.error(request, f'Error creating course: {str(e)}')
    
    # Get categories for dropdown - separate main categories and subcategories
    main_categories = Category.objects.filter(is_active=True, parent=None).order_by('display_order', 'name')
    subcategories = Category.objects.filter(is_active=True, parent__isnull=False).order_by('parent__name', 'display_order', 'name')
    
    context = get_context_data(request)
    context.update({
        'main_categories': main_categories,
        'subcategories': subcategories,
    })
    
    return render(request, 'platformadmin/course_create.html', context)


@platformadmin_required
def admin_course_edit(request, course_id):
    """Platform admin edits course details"""
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        try:
            old_values = {
                'title': course.title,
                'description': course.description,
                'price': str(course.price),
                'status': course.status,
            }
            
            # Update course
            course.title = request.POST.get('title')
            course.description = request.POST.get('description')
            course.short_description = request.POST.get('short_description', '')
            
            # Handle category selection - subcategory takes precedence over main category
            selected_category = request.POST.get('category')  # subcategory
            if not selected_category:
                selected_category = request.POST.get('main_category')  # main category fallback
            course.category_id = selected_category if selected_category else None
            
            course.level = request.POST.get('level')
            course.language = request.POST.get('language')
            course.price = request.POST.get('price', 0)
            course.discount_price = request.POST.get('discount_price') if request.POST.get('discount_price') else None
            course.is_free = request.POST.get('is_free') == 'on'
            course.allow_download = request.POST.get('allow_download') == 'on'
            course.status = request.POST.get('status', 'draft')
            course.is_featured = request.POST.get('is_featured') == 'on'
            
            if 'thumbnail' in request.FILES:
                course.thumbnail = request.FILES['thumbnail']
            
            course.save()
            
            # Log the action
            AdminLog.objects.create(
                admin=request.user,
                action='update',
                content_type='Course',
                object_id=str(course.id),
                object_repr=course.title,
                old_values=old_values,
                new_values={
                    'title': course.title,
                    'description': course.description,
                    'price': str(course.price),
                    'status': course.status,
                }
            )
            
            messages.success(request, 'Course updated successfully!')
            return redirect('platformadmin:admin_course_edit', course_id=course.id)
        except Exception as e:
            messages.error(request, f'Error updating course: {str(e)}')
    
    # Get categories - separate main categories and subcategories
    main_categories = Category.objects.filter(is_active=True, parent=None).order_by('display_order', 'name')
    subcategories = Category.objects.filter(is_active=True, parent__isnull=False).order_by('parent__name', 'display_order', 'name')
    
    # Get course modules and lessons
    modules = Module.objects.filter(course=course).prefetch_related('lessons').order_by('order')
    
    # Get course assignments (only active ones — exclude revoked or removed assignments)
    from apps.platformadmin.models import CourseAssignment
    assignments = CourseAssignment.objects.filter(
        course=course,
        status__in=['assigned', 'accepted']
    ).select_related('teacher', 'assigned_by').order_by('-assigned_at')
    
    # Get course stats
    from apps.courses.models import Enrollment
    from django.db.models import Sum
    student_count = Enrollment.objects.filter(course=course, status='active').count()
    total_revenue = Enrollment.objects.filter(
        course=course, 
        status='active'
    ).aggregate(total=Sum('payment_amount'))['total'] or 0
    
    context = get_context_data(request)
    context.update({
        'course': course,
        'main_categories': main_categories,
        'subcategories': subcategories,
        'modules': modules,
        'assignments': assignments,
        'student_count': student_count,
        'total_revenue': total_revenue,
    })
    
    return render(request, 'platformadmin/course_edit.html', context)


@platformadmin_required
def admin_course_delete(request, course_id):
    """Platform admin deletes a course"""
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        course_title = course.title
        course_id_str = str(course.id)
        
        # Log before deletion
        AdminLog.objects.create(
            admin=request.user,
            action='delete',
            content_type='Course',
            object_id=course_id_str,
            object_repr=course_title,
            old_values={
                'title': course.title,
                'status': course.status,
                'teacher': course.teacher.email if course.teacher else None,
            },
            new_values={},
        )
        
        course.delete()
        messages.success(request, f'Course "{course_title}" deleted successfully!')
        return redirect('platformadmin:course_management')
    
    context = get_context_data(request)
    context['course'] = course
    
    return render(request, 'platformadmin/course_delete_confirm.html', context)


@platformadmin_required
def admin_course_assign(request, course_id):
    """Assign a course to a teacher"""
    course = get_object_or_404(Course, id=course_id)
    from apps.platformadmin.models import CourseAssignment
    from apps.payments.models import Coupon
    from decimal import Decimal
    
    if request.method == 'POST':
        teacher_id = request.POST.get('teacher_id')
        teacher = get_object_or_404(User, id=teacher_id, role='teacher')
        
        # Check if already assigned
        existing = CourseAssignment.objects.filter(
            course=course, 
            teacher=teacher,
            status__in=['assigned', 'accepted']
        ).first()
        
        if existing:
            messages.warning(request, f'Course already assigned to {teacher.email}')
        else:
            # Get commission percentage (optional). If not provided, leave
            # as None so course assignment will use platform default.
            commission_percentage_raw = request.POST.get('commission_percentage')
            commission_percentage = None
            if commission_percentage_raw:
                try:
                    commission_percentage = Decimal(commission_percentage_raw)
                    if commission_percentage < 0 or commission_percentage > 100:
                        commission_percentage = None
                except Exception:
                    commission_percentage = None
            
            # Create assignment with accepted status (auto-assigned)
            from django.utils import timezone
            assignment = CourseAssignment.objects.create(
                course=course,
                teacher=teacher,
                assigned_by=request.user,
                status='accepted',
                accepted_at=timezone.now(),
                can_edit_content=request.POST.get('can_edit_content') == 'on',
                can_delete_content=request.POST.get('can_delete_content') == 'on',
                can_edit_details=request.POST.get('can_edit_details') == 'on',
                can_publish=request.POST.get('can_publish') == 'on',
                commission_percentage=commission_percentage,
                assignment_notes=request.POST.get('assignment_notes', ''),
            )
            
            # Update course teacher field
            if not course.teacher:
                course.teacher = teacher
                course.save()
            
            # Send notification to teacher
            from apps.notifications.models import Notification
            Notification.objects.create(
                user=teacher,
                notification_type='course_assignment',
                title='Course Assigned',
                message=f'You have been assigned to teach "{course.title}". You can now manage course content and students.',
                link_url='/courses/teacher/assignments/',
                link_text='View Assignment',
                course=course,
                send_email=True
            )
            
            # Log the action
            AdminLog.objects.create(
                admin=request.user,
                action='create',
                content_type='CourseAssignment',
                object_id=str(assignment.id),
                object_repr=f"{course.title} → {teacher.email}",
                new_values={
                    'course': course.title,
                    'teacher': teacher.email,
                    'status': assignment.status,
                    'commission_percentage': str(commission_percentage),
                 
                }
            )
            
            messages.success(request, 'Teacher assigned successfully.')
            return redirect('platformadmin:admin_course_edit', course_id=course.id)
    
    # Get all verified teachers
    teachers = User.objects.filter(
        role='teacher',
        is_active=True
    ).select_related('teacher_profile')
    
    # Get existing assignments for this course
    existing_assignments = CourseAssignment.objects.filter(
        course=course
    ).select_related('teacher').order_by('-assigned_at')
    
    context = get_context_data(request)
    context['course'] = course
    context['available_teachers'] = teachers
    context['existing_assignments'] = existing_assignments
    
    return render(request, 'platformadmin/course_assign.html', context)


@platformadmin_required
def admin_course_unassign(request, assignment_id):
    """Revoke a course assignment from a teacher"""
    from apps.platformadmin.models import CourseAssignment
    assignment = get_object_or_404(CourseAssignment, id=assignment_id)
    
    if request.method == 'POST':
        course_title = assignment.course.title
        teacher_email = assignment.teacher.email
        
        # Update assignment status
        assignment.status = 'revoked'
        assignment.revoked_at = timezone.now()
        assignment.save()
        
        # Log the action
        AdminLog.objects.create(
            admin=request.user,
            action='update',
            content_type='CourseAssignment',
            object_id=str(assignment.id),
            object_repr=f"{course_title} → {teacher_email}",
            old_values={'status': 'assigned'},
            new_values={'status': 'revoked'},
        )
        
        messages.success(request, f'Course "{course_title}" unassigned from {teacher_email}')
        return redirect('platformadmin:admin_course_edit', course_id=assignment.course.id)
    
    context = get_context_data(request)
    context['assignment'] = assignment
    
    return render(request, 'platformadmin/course_unassign_confirm.html', context)


@platformadmin_required
def admin_courses_list(request):
    """List all courses created by platform admin with comprehensive management features"""
    from apps.platformadmin.models import CourseAssignment
    from apps.courses.models import Enrollment
    
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    courses = Course.objects.select_related('teacher', 'category', 'created_by').prefetch_related('modules')
    
    # Apply filters
    if search:
        courses = courses.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(short_description__icontains=search) |
            Q(teacher__email__icontains=search) |
            Q(teacher__first_name__icontains=search) |
            Q(teacher__last_name__icontains=search)
        )
    
    if status_filter:
        courses = courses.filter(status=status_filter)
    
    if category_filter:
        courses = courses.filter(category_id=category_filter)
    
    # Sorting options
    valid_sort_fields = ['-created_at', 'created_at', '-updated_at', 'title', '-title', 
                        '-price', 'price', 'status']
    if sort_by in valid_sort_fields:
        courses = courses.order_by(sort_by)
    else:
        courses = courses.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(courses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    # Course statistics
    total_courses = Course.objects.count()
    published_courses = Course.objects.filter(status='published').count()
    draft_courses = Course.objects.filter(status='draft').count()
    archived_courses = Course.objects.filter(status='archived').count()
    free_courses = Course.objects.filter(is_free=True).count()
    paid_courses = Course.objects.filter(is_free=False).count()
    
    # Assignment statistics
    total_assignments = CourseAssignment.objects.count()
    pending_assignments = CourseAssignment.objects.filter(status='assigned').count()
    accepted_assignments = CourseAssignment.objects.filter(status='accepted').count()
    rejected_assignments = CourseAssignment.objects.filter(status='rejected').count()
    
    # Student enrollment statistics
    total_enrollments = Enrollment.objects.count()
    active_students = Enrollment.objects.values('student').distinct().count()
    
    # Revenue statistics
    from apps.payments.models import Payment
    total_revenue = Payment.objects.filter(
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_revenue = Payment.objects.filter(
        status='completed',
        created_at__gte=timezone.now() - timedelta(days=30)
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Annotate courses with student counts for the current page
    for course in page_obj.object_list:
        course.student_count = Enrollment.objects.filter(course=course).count()
        course.assignment_count = CourseAssignment.objects.filter(course=course).count()
        course.modules_count = course.modules.count()
    
    context = get_context_data(request)
    context.update({
        'page_obj': page_obj,
        'courses': page_obj.object_list,
        'search': search,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'sort_by': sort_by,
        'categories': categories,
        
        # Course statistics
        'total_courses': total_courses,
        'published_courses': published_courses,
        'draft_courses': draft_courses,
        'archived_courses': archived_courses,
        'free_courses': free_courses,
        'paid_courses': paid_courses,
        
        # Assignment statistics
        'total_assignments': total_assignments,
        'pending_assignments': pending_assignments,
        'accepted_assignments': accepted_assignments,
        'rejected_assignments': rejected_assignments,
        
        # Student statistics
        'total_enrollments': total_enrollments,
        'active_students': active_students,
        
        # Revenue statistics
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        
        # Feature flags
        'can_create_course': True,
        'can_assign_teachers': True,
        'can_delete_courses': True,
        'can_view_analytics': True,
    })
    
    return render(request, 'platformadmin/courses_list.html', context)


@platformadmin_required
def admin_view_all_assignments(request):
    """View all course assignments across platform with comprehensive analytics"""
    from apps.platformadmin.models import CourseAssignment
    
    # Get filters
    status_filter = request.GET.get('status', '')
    teacher_filter = request.GET.get('teacher', '')
    course_filter = request.GET.get('course', '')
    
    assignments = CourseAssignment.objects.select_related(
        'course', 'course__category', 'teacher', 'assigned_by', 'teacher__teacher_profile'
    )
    
    # Apply filters
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    
    if teacher_filter:
        assignments = assignments.filter(
            Q(teacher__email__icontains=teacher_filter) |
            Q(teacher__first_name__icontains=teacher_filter) |
            Q(teacher__last_name__icontains=teacher_filter)
        )
    
    if course_filter:
        assignments = assignments.filter(course__title__icontains=course_filter)
    
    # Pagination
    paginator = Paginator(assignments.order_by('-assigned_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Comprehensive statistics
    total_assignments = CourseAssignment.objects.count()
    pending_assignments = CourseAssignment.objects.filter(status='assigned').count()
    accepted_assignments = CourseAssignment.objects.filter(status='accepted').count()
    rejected_assignments = CourseAssignment.objects.filter(status='rejected').count()
    revoked_assignments = CourseAssignment.objects.filter(status='revoked').count()
    
    # Teacher statistics
    total_teachers_with_assignments = CourseAssignment.objects.values('teacher').distinct().count()
    
    # Course statistics
    total_courses_assigned = CourseAssignment.objects.values('course').distinct().count()
    
    # Recent assignments
    recent_assignments = CourseAssignment.objects.select_related(
        'course', 'teacher', 'assigned_by'
    ).order_by('-assigned_at')[:5]
    
    context = get_context_data(request)
    context.update({
        'page_obj': page_obj,
        'assignments': page_obj.object_list,
        'status_filter': status_filter,
        'teacher_filter': teacher_filter,
        'course_filter': course_filter,
        
        # Statistics
        'total_assignments': total_assignments,
        'pending_assignments': pending_assignments,
        'accepted_assignments': accepted_assignments,
        'rejected_assignments': rejected_assignments,
        'revoked_assignments': revoked_assignments,
        'total_teachers_with_assignments': total_teachers_with_assignments,
        'total_courses_assigned': total_courses_assigned,
        'recent_assignments': recent_assignments,
        
        # Pagination info
        'is_paginated': page_obj.has_other_pages(),
    })
    
    return render(request, 'platformadmin/assignments_list.html', context)


@platformadmin_required
def admin_category_management(request):
    """Manage course categories and subcategories"""
    search = request.GET.get('search', '')
    parent_filter = request.GET.get('parent', '')
    
    categories = Category.objects.prefetch_related('subcategories')
    
    # Apply filters
    if search:
        categories = categories.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search)
        )
    
    if parent_filter == 'main':
        categories = categories.filter(parent__isnull=True)
    elif parent_filter == 'sub':
        categories = categories.filter(parent__isnull=False)
    elif parent_filter:
        categories = categories.filter(parent_id=parent_filter)
    
    categories = categories.order_by('display_order', 'name')
    
    # Get main categories for filter dropdown
    main_categories = Category.objects.filter(parent__isnull=True, is_active=True)
    
    # Statistics
    total_categories = Category.objects.count()
    main_category_count = Category.objects.filter(parent__isnull=True).count()
    subcategory_count = Category.objects.filter(parent__isnull=False).count()
    active_categories = Category.objects.filter(is_active=True).count()
    
    # Courses per category
    from django.db.models import Count
    categories_with_counts = categories.annotate(
        course_count=Count('courses', filter=Q(courses__status='published'))
    )
    
    context = get_context_data(request)
    context.update({
        'categories': categories_with_counts,
        'main_categories': main_categories,
        'search': search,
        'parent_filter': parent_filter,
        'total_categories': total_categories,
        'main_category_count': main_category_count,
        'subcategory_count': subcategory_count,
        'active_categories': active_categories,
    })
    
    return render(request, 'platformadmin/category_management.html', context)


@platformadmin_required
def admin_category_create(request):
    """Create a new category or subcategory"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        icon = request.POST.get('icon', '')
        color = request.POST.get('color', '#667eea')
        parent_id = request.POST.get('parent')
        display_order = request.POST.get('display_order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        try:
            category = Category.objects.create(
                name=name,
                description=description,
                icon=icon,
                color=color,
                parent_id=parent_id if parent_id else None,
                display_order=display_order,
                is_active=is_active
            )
            
            # Log activity
            AdminLog.objects.create(
                admin=request.user,
                action='create_category',
                description=f'Created category: {category.name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect('platformadmin:admin_category_management')
        
        except Exception as e:
            messages.error(request, f'Error creating category: {str(e)}')
    
    # Get main categories for parent selection
    main_categories = Category.objects.filter(parent__isnull=True, is_active=True)
    
    context = get_context_data(request)
    context['main_categories'] = main_categories
    
    return render(request, 'platformadmin/category_create.html', context)


@platformadmin_required
def admin_category_edit(request, category_id):
    """Edit an existing category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.description = request.POST.get('description', '')
        category.icon = request.POST.get('icon', '')
        category.color = request.POST.get('color', '#667eea')
        category.display_order = request.POST.get('display_order', 0)
        category.is_active = request.POST.get('is_active') == 'on'
        
        parent_id = request.POST.get('parent')
        if parent_id:
            # Prevent circular reference
            if int(parent_id) != category.id:
                category.parent_id = parent_id
            else:
                messages.error(request, 'A category cannot be its own parent!')
                return redirect('platformadmin:admin_category_edit', category_id=category_id)
        else:
            category.parent = None
        
        try:
            category.save()
            
            # Log activity
            AdminLog.objects.create(
                admin=request.user,
                action='update_category',
                description=f'Updated category: {category.name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('platformadmin:admin_category_management')
        
        except Exception as e:
            messages.error(request, f'Error updating category: {str(e)}')
    
    # Get main categories for parent selection (excluding current category)
    main_categories = Category.objects.filter(
        parent__isnull=True, 
        is_active=True
    ).exclude(id=category_id)
    
    # Get category statistics
    course_count = Course.objects.filter(category=category).count()
    subcategory_count = category.subcategories.count()
    
    context = get_context_data(request)
    context.update({
        'category': category,
        'main_categories': main_categories,
        'course_count': course_count,
        'subcategory_count': subcategory_count,
    })
    
    return render(request, 'platformadmin/category_edit.html', context)


@platformadmin_required
def admin_category_delete(request, category_id):
    """Delete a category"""
    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        category_name = category.name

        # Capture old values for audit
        old_vals = {
            'name': category.name,
            'description': category.description,
            'parent_id': category.parent_id,
            'is_active': category.is_active,
        }

        # Delete the category
        category.delete()

        # Log the action
        try:
            AdminLog.objects.create(
                admin=request.user,
                action='delete_category',
                content_type='Category',
                object_id=str(category_id),
                object_repr=category_name,
                old_values=old_vals,
                new_values={},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        except Exception:
            # Ensure deletion still succeeds even if logging fails
            pass

        messages.success(request, f'Category "{category_name}" deleted successfully!')
        return redirect('platformadmin:admin_category_management')

    context = get_context_data(request)
    context['category'] = category

    return render(request, 'platformadmin/category_delete_confirm.html', context)


# ==================== PLATFORM ADMIN MODULE MANAGEMENT ====================

@platformadmin_required
def admin_module_create(request, course_id):
    """Create a new module for a course (Platform Admin)"""
    from django.db.models import Max
    
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        # Get the highest order number
        max_order = Module.objects.filter(course=course).aggregate(Max('order'))['order__max'] or 0
        
        # Create module
        module = Module.objects.create(
            course=course,
            title=request.POST.get('title'),
            description=request.POST.get('description', ''),
            order=max_order + 1,
            is_published=request.POST.get('is_published') == 'on'
        )
        
        # Log the action
        AdminLog.objects.create(
            admin=request.user,
            action='create',
            content_type='Module',
            object_id=str(module.id),
            object_repr=module.title,
            old_values={},
            new_values={
                'title': module.title,
                'course': course.title,
            }
        )
        
        messages.success(request, f'Module "{module.title}" created successfully!')
        return redirect('platformadmin:admin_course_edit', course_id=course.id)
    
    return redirect('platformadmin:admin_course_edit', course_id=course.id)


@platformadmin_required
def admin_module_edit(request, module_id):
    """Edit an existing module (Platform Admin)"""
    module = get_object_or_404(Module, id=module_id)
    
    if request.method == 'POST':
        old_values = {
            'title': module.title,
            'description': module.description,
            'is_published': module.is_published,
        }
        
        module.title = request.POST.get('title')
        module.description = request.POST.get('description', '')
        module.is_published = request.POST.get('is_published') == 'on'
        module.save()
        
        # Log the action
        AdminLog.objects.create(
            admin=request.user,
            action='update',
            content_type='Module',
            object_id=str(module.id),
            object_repr=module.title,
            old_values=old_values,
            new_values={
                'title': module.title,
                'description': module.description,
                'is_published': module.is_published,
            }
        )
        
        messages.success(request, f'Module "{module.title}" updated successfully!')
        return redirect('platformadmin:admin_course_edit', course_id=module.course.id)
    
    return redirect('platformadmin:admin_course_edit', course_id=module.course.id)


@platformadmin_required
def admin_module_delete(request, module_id):
    """Delete a module (Platform Admin)"""
    module = get_object_or_404(Module, id=module_id)
    course_id = module.course.id
    module_title = module.title
    
    if request.method == 'POST':
        # Log the action before deletion
        AdminLog.objects.create(
            admin=request.user,
            action='delete',
            content_type='Module',
            object_id=str(module.id),
            object_repr=module_title,
            old_values={
                'title': module.title,
                'course': module.course.title,
            },
            new_values={}
        )
        
        module.delete()
        messages.success(request, f'Module "{module_title}" deleted successfully!')
        return redirect('platformadmin:admin_course_edit', course_id=course_id)
    
    return redirect('platformadmin:admin_course_edit', course_id=course_id)


@platformadmin_required
def admin_module_reorder(request, course_id):
    """Reorder modules (Platform Admin)"""
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            module_order = data.get('module_order', [])
            
            for index, module_id in enumerate(module_order):
                Module.objects.filter(id=module_id, course=course).update(order=index)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ==================== PLATFORM ADMIN LESSON MANAGEMENT ====================

@platformadmin_required
def admin_lesson_create(request, module_id):
    """Create a new lesson for a module (Platform Admin)"""
    from apps.courses.models import Lesson, LessonMedia
    from django.db.models import Max
    
    module = get_object_or_404(Module, id=module_id)
    
    if request.method == 'POST':
        # Get the highest order number
        max_order = Lesson.objects.filter(module=module).aggregate(Max('order'))['order__max'] or 0
        
        # Get common lesson data
        base_title = request.POST.get('title')
        description = request.POST.get('description', '')
        lesson_type = request.POST.get('lesson_type', 'audio')
        is_free_preview = request.POST.get('is_free_preview') == 'on'
        is_published = request.POST.get('is_published') == 'on'
        text_content = request.POST.get('text_content', '')
        
        # Handle multiple media files - create separate lesson for each file
        media_files = request.FILES.getlist('media_files')
        if media_files:
            created_lessons = []
            for index, media_file in enumerate(media_files):
                # Determine media type based on file extension
                file_extension = media_file.name.split('.')[-1].lower()
                if file_extension in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                    media_type = 'video'
                    actual_lesson_type = 'video'
                else:
                    media_type = 'audio'
                    actual_lesson_type = 'audio'
                
                # Create individual lesson for each file
                if len(media_files) > 1:
                    lesson_title = f"{base_title} - Part {index + 1}"
                else:
                    lesson_title = base_title
                
                lesson = Lesson.objects.create(
                    module=module,
                    course=module.course,
                    title=lesson_title,
                    description=description,
                    lesson_type=actual_lesson_type,
                    order=max_order + index + 1,
                    is_free_preview=is_free_preview,
                    is_published=is_published,
                    text_content=text_content
                )
                
                # Attach media file to this lesson
                LessonMedia.objects.create(
                    lesson=lesson,
                    media_file=media_file,
                    media_type=media_type,
                    file_size=media_file.size,
                    order=0
                )
                
                created_lessons.append(lesson)
            
            # Use the first lesson for logging
            lesson = created_lessons[0]
        else:
            # Create single lesson without media files (for text lessons or legacy single file)
            lesson = Lesson.objects.create(
                module=module,
                course=module.course,
                title=base_title,
                description=description,
                lesson_type=lesson_type,
                order=max_order + 1,
                is_free_preview=is_free_preview,
                is_published=is_published,
                text_content=text_content
            )
            
            # Handle file upload if provided (legacy single file)
            if 'audio_file' in request.FILES:
                audio_file = request.FILES['audio_file']
                lesson.audio_file = audio_file
                lesson.file_size = audio_file.size
                lesson.save()
        
        # Log the action
        AdminLog.objects.create(
            admin=request.user,
            action='create',
            content_type='Lesson',
            object_id=str(lesson.id),
            object_repr=lesson.title,
            old_values={},
            new_values={
                'title': lesson.title,
                'module': module.title,
                'course': module.course.title,
            }
        )
        
        if media_files and len(media_files) > 1:
            messages.success(request, f'{len(media_files)} lessons created successfully from uploaded media files!')
        else:
            messages.success(request, f'Lesson "{lesson.title}" created successfully!')
        return redirect('platformadmin:admin_course_edit', course_id=module.course.id)
    
    return redirect('platformadmin:admin_course_edit', course_id=module.course.id)


@platformadmin_required
def admin_lesson_edit(request, lesson_id):
    """Edit an existing lesson (Platform Admin)"""
    from apps.courses.models import Lesson, LessonMedia
    from django.db.models import Max
    
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    if request.method == 'POST':
        old_values = {
            'title': lesson.title,
            'description': lesson.description,
            'lesson_type': lesson.lesson_type,
        }
        
        lesson.title = request.POST.get('title')
        lesson.description = request.POST.get('description', '')
        lesson.lesson_type = request.POST.get('lesson_type', 'audio')
        lesson.is_free_preview = request.POST.get('is_free_preview') == 'on'
        lesson.is_published = request.POST.get('is_published') == 'on'
        lesson.text_content = request.POST.get('text_content', '')
        
        # Handle file upload if provided (legacy single file)
        if 'audio_file' in request.FILES:
            audio_file = request.FILES['audio_file']
            lesson.audio_file = audio_file
            lesson.file_size = audio_file.size
        
        lesson.save()
        
        # Handle multiple media files
        media_files = request.FILES.getlist('media_files')
        if media_files:
            # Get the current max order
            max_order = LessonMedia.objects.filter(lesson=lesson).aggregate(Max('order'))['order__max'] or -1
            
            for index, media_file in enumerate(media_files):
                # Determine media type based on file extension
                file_extension = media_file.name.split('.')[-1].lower()
                if file_extension in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                    media_type = 'video'
                else:
                    media_type = 'audio'
                
                LessonMedia.objects.create(
                    lesson=lesson,
                    media_file=media_file,
                    media_type=media_type,
                    file_size=media_file.size,
                    order=max_order + index + 1
                )
        
        # Log the action
        AdminLog.objects.create(
            admin=request.user,
            action='update',
            content_type='Lesson',
            object_id=str(lesson.id),
            object_repr=lesson.title,
            old_values=old_values,
            new_values={
                'title': lesson.title,
                'description': lesson.description,
                'lesson_type': lesson.lesson_type,
            }
        )
        
        messages.success(request, f'Lesson "{lesson.title}" updated successfully!')
        return redirect('platformadmin:admin_course_edit', course_id=lesson.course.id)
    
    return redirect('platformadmin:admin_course_edit', course_id=lesson.course.id)


@platformadmin_required
def admin_lesson_delete(request, lesson_id):
    """Delete a lesson (Platform Admin)"""
    from apps.courses.models import Lesson
    
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course_id = lesson.course.id
    lesson_title = lesson.title
    
    if request.method == 'POST':
        # Log the action before deletion
        AdminLog.objects.create(
            admin=request.user,
            action='delete',
            content_type='Lesson',
            object_id=str(lesson.id),
            object_repr=lesson_title,
            old_values={
                'title': lesson.title,
                'course': lesson.course.title,
            },
            new_values={}
        )
        
        lesson.delete()
        messages.success(request, f'Lesson "{lesson_title}" deleted successfully!')
        return redirect('platformadmin:admin_course_edit', course_id=course_id)
    
    return redirect('platformadmin:admin_course_edit', course_id=course_id)


@platformadmin_required
def admin_lesson_reorder(request, module_id):
    """Reorder lessons within a module (Platform Admin)"""
    from apps.courses.models import Lesson
    
    module = get_object_or_404(Module, id=module_id)
    
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            lesson_order = data.get('lesson_order', [])
            
            for index, lesson_id in enumerate(lesson_order):
                Lesson.objects.filter(id=lesson_id, module=module).update(order=index)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@platformadmin_required
def admin_lesson_media_delete(request, media_id):
    """Delete a lesson media file (Platform Admin)"""
    from apps.courses.models import LessonMedia
    
    media = get_object_or_404(LessonMedia, id=media_id)

    if request.method == 'POST':

        # Log the action before deletion
        AdminLog.objects.create(
            admin=request.user,
            action='delete',
            content_type='LessonMedia',
            object_id=str(media.id),
            object_repr=f'Media file for {media.lesson.title}',
            old_values={
                'lesson': media.lesson.title,
                'media_type': media.media_type,
            },
            new_values={}
        )
        
        media.delete()
        messages.success(request, 'Media file deleted successfully!')
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


# =============================================================================
# Free User Management Views
# =============================================================================

@platformadmin_required
@platformadmin_required
@require_http_methods(['GET'])
def free_users_list(request):
    """List all free users"""
    from apps.platformadmin.models import FreeUser
    
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'all')
    
    # Base queryset
    free_users = FreeUser.objects.select_related('user', 'assigned_by').order_by('-assigned_at')
    
    # Apply filters
    if search:
        free_users = free_users.filter(
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    
    if status_filter == 'active':
        free_users = free_users.filter(is_active=True)
    elif status_filter == 'inactive':
        free_users = free_users.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(free_users, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    # Statistics
    stats = {
        'total': FreeUser.objects.count(),
        'active': FreeUser.objects.filter(is_active=True).count(),
        'inactive': FreeUser.objects.filter(is_active=False).count(),
        'expired': FreeUser.objects.filter(
            is_active=True,
            expires_at__lt=timezone.now()
        ).count(),
    }
    
    context = get_context_data(request)
    context.update({
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'stats': stats,
    })
    
    return render(request, 'platformadmin/free_users_list.html', context)


@platformadmin_required
@require_http_methods(['GET'])
def select_user_for_free_access(request):
    """Select a user to assign free access"""
    from apps.platformadmin.models import FreeUser
    
    search = request.GET.get('search', '').strip()
    
    # Get students who are not already free users
    existing_free_user_ids = FreeUser.objects.filter(is_active=True).values_list('user_id', flat=True)
    users = User.objects.filter(role='student', is_active=True).exclude(id__in=existing_free_user_ids)
    
    # Apply search
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(users.order_by('first_name', 'email'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = get_context_data(request)
    context.update({
        'page_obj': page_obj,
        'search': search,
    })
    
    return render(request, 'platformadmin/select_user_for_free_access.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def assign_free_user(request, user_id):
    """Assign free access to a user"""
    from apps.platformadmin.models import FreeUser
    
    user = get_object_or_404(User, id=user_id, role='student')
    
    # Check if already a free user
    existing_free_user = FreeUser.objects.filter(user=user).first()
    
    if request.method == 'POST':
        if existing_free_user:
            # Update existing record
            existing_free_user.is_active = True
            existing_free_user.reason = request.POST.get('reason', '')
            existing_free_user.assigned_by = request.user
            
            expires_at = request.POST.get('expires_at')
            if expires_at:
                try:
                    from datetime import datetime
                    existing_free_user.expires_at = datetime.fromisoformat(expires_at)
                except ValueError:
                    existing_free_user.expires_at = None
            else:
                existing_free_user.expires_at = None
            
            max_courses = request.POST.get('max_courses')
            if max_courses and max_courses.isdigit():
                existing_free_user.max_courses = int(max_courses)
            else:
                existing_free_user.max_courses = None
            
            existing_free_user.save()
            action = 'update'
            
        else:
            # Create new free user record
            expires_at = request.POST.get('expires_at')
            expires_at_parsed = None
            if expires_at:
                try:
                    from datetime import datetime
                    expires_at_parsed = datetime.fromisoformat(expires_at)
                except ValueError:
                    pass
            
            max_courses = request.POST.get('max_courses')
            max_courses_parsed = None
            if max_courses and max_courses.isdigit():
                max_courses_parsed = int(max_courses)
            
            FreeUser.objects.create(
                user=user,
                assigned_by=request.user,
                is_active=True,
                reason=request.POST.get('reason', ''),
                expires_at=expires_at_parsed,
                max_courses=max_courses_parsed
            )
            action = 'create'
        
        # Log the action
        AdminLog.objects.create(
            admin=request.user,
            action=action,
            content_type='FreeUser',
            object_id=str(user.id),
            object_repr=f"Free User: {user.email}",
            old_values={},
            new_values={
                'user': user.email,
                'reason': request.POST.get('reason', ''),
                'expires_at': request.POST.get('expires_at'),
                'max_courses': request.POST.get('max_courses'),
            }
        )
        
        messages.success(request, f'Free access assigned to {user.email} successfully!')
        return redirect('platformadmin:free_users_list')
    
    context = get_context_data(request)
    context.update({
        'user': user,
        'existing_free_user': existing_free_user,
        'active_enrollments_count': user.enrollments.filter(status='active').count(),
    })
    
    return render(request, 'platformadmin/assign_free_user.html', context)


@platformadmin_required
@require_http_methods(['POST'])
def remove_free_user(request, user_id):
    """Remove free access from a user"""
    from apps.platformadmin.models import FreeUser
    
    user = get_object_or_404(User, id=user_id)
    free_user = get_object_or_404(FreeUser, user=user)
    
    # Log the action before removal
    AdminLog.objects.create(
        admin=request.user,
        action='delete',
        content_type='FreeUser',
        object_id=str(free_user.id),
        object_repr=f"Free User: {user.email}",
        old_values={
            'user': user.email,
            'is_active': free_user.is_active,
            'reason': free_user.reason,
        },
        new_values={}
    )
    
    free_user.delete()
    messages.success(request, f'Free access removed from {user.email}!')
    return redirect('platformadmin:free_users_list')


@platformadmin_required
@require_http_methods(['POST'])
def toggle_free_user_status(request, user_id):
    """Toggle active status of free user"""
    from apps.platformadmin.models import FreeUser
    
    user = get_object_or_404(User, id=user_id)
    free_user = get_object_or_404(FreeUser, user=user)
    
    old_status = free_user.is_active
    free_user.is_active = not free_user.is_active
    free_user.save()
    
    # Log the action
    AdminLog.objects.create(
        admin=request.user,
        action='update',
        content_type='FreeUser',
        object_id=str(free_user.id),
        object_repr=f"Free User: {user.email}",
        old_values={'is_active': old_status},
        new_values={'is_active': free_user.is_active}
    )
    
    status_text = 'activated' if free_user.is_active else 'deactivated'
    messages.success(request, f'Free access {status_text} for {user.email}!')
    return redirect('platformadmin:free_users_list')



