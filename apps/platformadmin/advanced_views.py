"""
Advanced platformadmin views for bulk operations, CSV exports, and analytics
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.utils import timezone

from apps.platformadmin.decorators import platformadmin_required
from apps.platformadmin.permissions import permission_required, AdminPermissions
from apps.platformadmin.forms import BulkUserActionForm, BulkRefundForm, RefundForm
from apps.platformadmin.export_utils import CSVExporter
from apps.platformadmin.payment_handlers import BulkPaymentHandler
from apps.platformadmin.notifications import AdminEmailNotifier
from apps.platformadmin.utils import ActivityLog, get_context_data
from apps.payments.models import Payment, Refund
from apps.courses.models import Course, Enrollment
from django.contrib.auth import get_user_model

User = get_user_model()


@platformadmin_required
@permission_required(AdminPermissions.MANAGE_USERS)
@require_POST
def bulk_user_action(request):
    """Handle bulk user actions"""
    form = BulkUserActionForm(request.POST)
    
    if form.is_valid():
        user_ids = form.cleaned_data['user_ids'].split(',')
        action = form.cleaned_data['action']
        reason = form.cleaned_data.get('reason', '')
        
        users = User.objects.filter(id__in=user_ids)
        success_count = 0
        failed_count = 0
        
        with transaction.atomic():
            for user in users:
                try:
                    old_values = {'is_active': user.is_active}
                    
                    if action == 'activate':
                        user.is_active = True
                        user.save()
                        # Send notification
                        AdminEmailNotifier.notify_user_activated(user, request.user)
                        success_count += 1
                    
                    elif action == 'deactivate':
                        user.is_active = False
                        user.save()
                        AdminEmailNotifier.notify_user_deactivated(user, request.user, reason)
                        success_count += 1
                    
                    elif action == 'verify_teachers' and user.role == 'teacher':
                        if hasattr(user, 'teacher_profile'):
                            user.teacher_profile.is_verified = True
                            user.teacher_profile.verification_date = timezone.now()
                            user.teacher_profile.save()
                            AdminEmailNotifier.notify_teacher_verified(user, request.user)
                            success_count += 1
                    
                    elif action == 'send_email':
                        # Email will be sent to all users
                        success_count += 1
                    
                    # Log action
                    new_values = {'is_active': user.is_active}
                    ActivityLog.log_user_action(user, request.user, action, old_values, new_values, reason)
                
                except Exception as e:
                    failed_count += 1
                    continue
        
        # Send bulk email if requested
        if action == 'send_email' and reason:
            user_emails = [u.email for u in users]
            AdminEmailNotifier.send_bulk_email(
                user_emails=user_emails,
                subject='Message from Platform Administration',
                message=reason
            )
        
        messages.success(request, f'Bulk action completed: {success_count} successful, {failed_count} failed')
    else:
        messages.error(request, 'Invalid form data')
    
    return redirect('platformadmin:user_management')


@platformadmin_required
@permission_required(AdminPermissions.PROCESS_REFUNDS)
@require_POST
def bulk_refund_action(request):
    """Handle bulk refund processing"""
    form = BulkRefundForm(request.POST)
    
    if form.is_valid():
        payment_ids = form.cleaned_data['payment_ids'].split(',')
        refund_reason = form.cleaned_data['refund_reason']
        admin_notes = form.cleaned_data['admin_notes']
        
        handler = BulkPaymentHandler()
        results = handler.bulk_refund(
            payment_ids=payment_ids,
            admin_user=request.user,
            reason=refund_reason,
            admin_notes=admin_notes
        )
        
        messages.success(
            request,
            f'Bulk refund completed: {results["successful"]} successful, {results["failed"]} failed'
        )
    else:
        messages.error(request, 'Invalid form data')
    
    return redirect('platformadmin:payment_management')


@platformadmin_required
@permission_required(AdminPermissions.EXPORT_DATA)
def export_users_csv(request):
    """Export users to CSV"""
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    users = User.objects.exclude(role='admin')
    
    if role_filter in ['student', 'teacher']:
        users = users.filter(role=role_filter)
    
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    if search:
        from django.db.models import Q
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    return CSVExporter.export_users(users)


@platformadmin_required
@permission_required(AdminPermissions.EXPORT_DATA)
def export_courses_csv(request):
    """Export courses to CSV"""
    status = request.GET.get('status', '')
    category = request.GET.get('category', '')
    
    courses = Course.objects.select_related('teacher', 'category')
    
    if status:
        courses = courses.filter(status=status)
    if category:
        courses = courses.filter(category_id=category)
    
    return CSVExporter.export_courses(courses)


@platformadmin_required
@permission_required(AdminPermissions.EXPORT_DATA)
def export_payments_csv(request):
    """Export payments to CSV"""
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    payments = Payment.objects.select_related('user', 'course')
    
    if status:
        payments = payments.filter(status=status)
    if date_from:
        payments = payments.filter(created_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(created_at__date__lte=date_to)
    
    return CSVExporter.export_payments(payments)


@platformadmin_required
@permission_required(AdminPermissions.EXPORT_DATA)
def export_refunds_csv(request):
    """Export refunds to CSV"""
    status = request.GET.get('status', '')
    
    refunds = Refund.objects.select_related('payment', 'user', 'processed_by')
    
    if status:
        refunds = refunds.filter(status=status)
    
    return CSVExporter.export_refunds(refunds)


@platformadmin_required
@permission_required(AdminPermissions.EXPORT_DATA)
def export_admin_logs_csv(request):
    """Export admin activity logs to CSV"""
    from apps.platformadmin.models import AdminLog
    
    admin_id = request.GET.get('admin', '')
    action = request.GET.get('action', '')
    
    logs = AdminLog.objects.select_related('admin')
    
    if admin_id:
        logs = logs.filter(admin_id=admin_id)
    if action:
        logs = logs.filter(action=action)
    
    return CSVExporter.export_admin_logs(logs)


@platformadmin_required
@permission_required(AdminPermissions.VIEW_ANALYTICS)
def advanced_analytics(request):
    """Advanced analytics dashboard"""
    from apps.platformadmin.payment_handlers import PaymentAnalytics
    from datetime import timedelta
    
    # Get date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Get analytics data
    refund_stats = PaymentAnalytics.get_refund_statistics(start_date, end_date)
    payment_disputes = PaymentAnalytics.get_payment_disputes()
    
    # Revenue analytics
    from apps.platformadmin.utils import ReportGenerator
    revenue_report = ReportGenerator.get_revenue_report(start_date, end_date)
    user_report = ReportGenerator.get_user_report(start_date, end_date)
    
    context = get_context_data(request)
    context.update({
        'refund_stats': refund_stats,
        'payment_disputes': payment_disputes,
        'revenue_report': revenue_report,
        'user_report': user_report,
        'start_date': start_date,
        'end_date': end_date,
    })
    
    return render(request, 'platformadmin/advanced_analytics.html', context)


@platformadmin_required
@permission_required(AdminPermissions.VIEW_ANALYTICS)
def teacher_analytics(request):
    """Teacher performance analytics"""
    teachers = User.objects.filter(role='teacher', is_active=True).select_related('teacher_profile')
    
    # Get teacher stats
    teacher_stats = []
    for teacher in teachers:
        courses = Course.objects.filter(teacher=teacher) if hasattr(Course, 'objects') else []
        total_revenue = Payment.objects.filter(
            course__teacher=teacher,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        teacher_stats.append({
            'teacher': teacher,
            'total_courses': courses.count() if courses else 0,
            'published_courses': courses.filter(status='published').count() if courses else 0,
            'total_students': teacher.teacher_profile.total_students if hasattr(teacher, 'teacher_profile') else 0,
            'total_revenue': total_revenue,
            'is_verified': teacher.teacher_profile.is_verified if hasattr(teacher, 'teacher_profile') else False,
        })
    
    # Sort by total revenue
    teacher_stats.sort(key=lambda x: x['total_revenue'], reverse=True)
    
    context = get_context_data(request)
    context['teacher_stats'] = teacher_stats
    
    return render(request, 'platformadmin/teacher_analytics.html', context)


@platformadmin_required
def system_health(request):
    """System health and monitoring dashboard"""
    from apps.platformadmin.payment_handlers import PaymentAnalytics
    
    # Get system health metrics
    disputes = PaymentAnalytics.get_payment_disputes()
    
    # Check for issues
    issues = []
    if disputes['old_pending_payments'] > 10:
        issues.append({
            'severity': 'warning',
            'message': f"{disputes['old_pending_payments']} pending payments older than 24 hours"
        })
    
    if disputes['recent_failed_payments'] > 20:
        issues.append({
            'severity': 'error',
            'message': f"{disputes['recent_failed_payments']} failed payments in the last 7 days"
        })
    
    if disputes['pending_refund_requests'] > 5:
        issues.append({
            'severity': 'warning',
            'message': f"{disputes['pending_refund_requests']} pending refund requests"
        })
    
    context = get_context_data(request)
    context.update({
        'issues': issues,
        'disputes': disputes,
    })
    
    return render(request, 'platformadmin/system_health.html', context)


@platformadmin_required
@require_POST
def clear_cache(request):
    """Clear platform cache"""
    from django.core.cache import cache
    from apps.platformadmin.utils import DashboardStats
    
    try:
        DashboardStats.clear_cache()
        cache.clear()
        messages.success(request, 'Cache cleared successfully')
    except Exception as e:
        messages.error(request, f'Error clearing cache: {str(e)}')
    
    return redirect('platformadmin:dashboard')
