"""
Advanced platformadmin views for bulk operations, CSV exports, and analytics
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta

from apps.platformadmin.decorators import platformadmin_required
from apps.platformadmin.permissions import permission_required, AdminPermissions
from apps.platformadmin.forms import BulkUserActionForm, BulkRefundForm, RefundForm
from apps.platformadmin.export_utils import CSVExporter
from apps.platformadmin.payment_handlers import BulkPaymentHandler
from apps.platformadmin.notifications import AdminEmailNotifier
from apps.platformadmin.utils import ActivityLog, get_context_data
from apps.payments.models import Payment, Refund, CouponUsage
from apps.payments.commission_calculator import CommissionCalculator
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
    teachers_qs = User.objects.filter(role='teacher', is_active=True).select_related('teacher_profile')

    # GET params for optional sorting/period filtering
    sort_by = request.GET.get('sort_by', 'revenue')
    period = request.GET.get('period', 'all')

    # Determine start date based on period
    start_dt = None
    if period == 'month':
        start_dt = timezone.now() - timedelta(days=30)
    elif period == 'quarter':
        start_dt = timezone.now() - timedelta(days=90)
    elif period == 'year':
        start_dt = timezone.now() - timedelta(days=365)

    # Build enriched teacher objects with attached stats so template can reference attributes
    enriched_teachers = []
    for teacher in teachers_qs:
        # Courses and enrollments
        courses_qs = Course.objects.filter(teacher=teacher)
        if start_dt is not None:
            # filter courses created within the period if created_at exists
            try:
                courses_qs = courses_qs.filter(created_at__gte=start_dt)
            except Exception:
                pass
        course_count = courses_qs.count()
        published_count = courses_qs.filter(status='published').count()
        total_enrollments_qs = Enrollment.objects.filter(course__teacher=teacher)
        if start_dt is not None:
            try:
                total_enrollments_qs = total_enrollments_qs.filter(created_at__gte=start_dt)
            except Exception:
                pass
        total_enrollments = total_enrollments_qs.count()

        # Revenue - Calculate actual teacher earnings using commission calculator
        payments_qs = Payment.objects.filter(
            course__teacher=teacher,
            status='completed'
        ).select_related('course')
        if start_dt is not None:
            try:
                payments_qs = payments_qs.filter(created_at__gte=start_dt)
            except Exception:
                pass

        # Calculate actual teacher revenue (not total sales)
        from decimal import Decimal
        total_sales = Decimal('0')
        teacher_net_revenue = Decimal('0')
        
        for payment in payments_qs:
            total_sales += payment.amount
            
            # Get coupon usage if any
            coupon_usage = CouponUsage.objects.filter(payment=payment).first()
            coupon = coupon_usage.coupon if coupon_usage else None
            
            # Calculate commission using the commission calculator
            commission_data = CommissionCalculator.calculate_commission(payment, coupon)
            teacher_net_revenue += commission_data['teacher_revenue']
        
        total_revenue = teacher_net_revenue  # Show net revenue to teachers, not total sales

        # Basic rating / verification data
        total_students = getattr(teacher, 'total_students', None)
        if hasattr(teacher, 'teacher_profile'):
            total_students = teacher.teacher_profile.total_students if getattr(teacher.teacher_profile, 'total_students', None) is not None else total_students
            is_verified = getattr(teacher.teacher_profile, 'is_verified', False)
        else:
            is_verified = False

        # Simple performance score: weighted revenue + enrollments (scaled)
        performance_score = 0
        try:
            performance_score = int(min(100, (total_revenue / 1000) + (total_enrollments * 0.5)))
        except Exception:
            performance_score = 0

        # Attach attributes to teacher instance for template use
        setattr(teacher, 'course_count', course_count)
        setattr(teacher, 'total_enrollments', total_enrollments)
        setattr(teacher, 'total_revenue', total_revenue)
        setattr(teacher, 'avg_rating', getattr(teacher, 'avg_rating', 0))
        setattr(teacher, 'performance_score', performance_score)

        enriched_teachers.append(teacher)

    # Sort according to requested sort_by
    if sort_by == 'revenue':
        enriched_teachers.sort(key=lambda t: getattr(t, 'total_revenue', 0), reverse=True)
    elif sort_by == 'enrollments':
        enriched_teachers.sort(key=lambda t: getattr(t, 'total_enrollments', 0), reverse=True)
    elif sort_by == 'courses':
        enriched_teachers.sort(key=lambda t: getattr(t, 'course_count', 0), reverse=True)

    # Overall metrics
    total_teachers = teachers_qs.count()
    active_teachers = teachers_qs.filter(is_active=True).count()
    verified_teachers = sum(1 for t in teachers_qs if hasattr(t, 'teacher_profile') and getattr(t.teacher_profile, 'is_verified', False))
    total_courses_qs = Course.objects.filter(teacher__in=teachers_qs)
    total_payments_qs = Payment.objects.filter(course__teacher__in=teachers_qs, status='completed')
    if start_dt is not None:
        try:
            total_courses_qs = total_courses_qs.filter(created_at__gte=start_dt)
        except Exception:
            pass
        try:
            total_payments_qs = total_payments_qs.filter(created_at__gte=start_dt)
        except Exception:
            pass

    total_courses = total_courses_qs.count()
    total_revenue_all = total_payments_qs.aggregate(total=Sum('amount'))['total'] or 0
    avg_rating = 0

    # Performance distribution and top earners
    perf_counts = {'excellent': 0, 'good': 0, 'average': 0, 'poor': 0}
    top_earners = enriched_teachers[:5]
    for t in enriched_teachers:
        score = getattr(t, 'performance_score', 0)
        if score >= 80:
            perf_counts['excellent'] += 1
        elif score >= 60:
            perf_counts['good'] += 1
        elif score >= 40:
            perf_counts['average'] += 1
        else:
            perf_counts['poor'] += 1

    performance_distribution = [perf_counts['excellent'], perf_counts['good'], perf_counts['average'], perf_counts['poor']]
    top_earner_names = [t.get_full_name() for t in top_earners]
    top_earner_revenue = [getattr(t, 'total_revenue', 0) for t in top_earners]

    # Recent activities - try to use ActivityLog if available
    recent_activities = []
    try:
        recent_activities = ActivityLog.get_recent_teacher_activities() if hasattr(ActivityLog, 'get_recent_teacher_activities') else []
    except Exception:
        recent_activities = []

    context = get_context_data(request)
    context.update({
        'teachers': enriched_teachers,
        'total_teachers': total_teachers,
        'active_teachers': active_teachers,
        'verified_teachers': verified_teachers,
        'total_courses': total_courses,
        'total_revenue': total_revenue_all,
        'avg_rating': avg_rating,
        'performance_distribution': performance_distribution,
        'top_earner_names': top_earner_names,
        'top_earner_revenue': top_earner_revenue,
        'recent_activities': recent_activities,
        'sort_by': sort_by,
        'period': period,
    })

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
    """Cache clearing functionality removed"""
    messages.info(request, 'Cache system has been disabled. No cache to clear.')
    return redirect('platformadmin:analytics')
    
    return redirect('platformadmin:dashboard')
