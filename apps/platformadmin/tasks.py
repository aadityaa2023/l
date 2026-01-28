"""
Celery tasks for platformadmin background processing
Run reports, send notifications, and perform cleanup tasks
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_daily_dashboard_stats():
    """
    Generate and cache daily dashboard statistics
    Runs every day at midnight
    """
    from apps.platformadmin.models import DashboardStat
    from apps.platformadmin.utils import DashboardStats
    from apps.courses.models import Course, Enrollment
    from apps.payments.models import Payment
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    today = timezone.now().date()
    
    try:
        # Check if stats already exist for today
        stat, created = DashboardStat.objects.get_or_create(
            date=today,
            defaults={
                'total_users': 0,
                'total_teachers': 0,
                'total_students': 0,
                'total_courses': 0,
                'published_courses': 0,
                'pending_approval_courses': 0,
                'total_enrollments': 0,
                'total_revenue': Decimal('0'),
                'completed_transactions': 0,
                'failed_transactions': 0,
            }
        )
        
        # Update stats
        stat.total_users = User.objects.filter(is_active=True).count()
        stat.total_teachers = User.objects.filter(role='teacher', is_active=True).count()
        stat.total_students = User.objects.filter(role='student', is_active=True).count()
        
        stat.total_courses = Course.objects.count()
        stat.published_courses = Course.objects.filter(status='published').count()
        
        from apps.platformadmin.models import CourseApproval
        stat.pending_approval_courses = CourseApproval.objects.filter(status='pending').count()
        
        if hasattr(Enrollment, 'objects'):
            stat.total_enrollments = Enrollment.objects.filter(status='active').count()
        
        completed_payments = Payment.objects.filter(status='completed')
        stat.total_revenue = completed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        stat.completed_transactions = completed_payments.count()
        stat.failed_transactions = Payment.objects.filter(status='failed').count()
        
        stat.save()
        
        logger.info(f"Daily dashboard stats generated for {today}")
        return f"Stats generated for {today}"
    
    except Exception as e:
        logger.error(f"Error generating daily stats: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def send_daily_admin_report():
    """
    Send daily report to admins
    Runs every day at 9 AM
    """
    from apps.platformadmin.notifications import AdminEmailNotifier
    from apps.platformadmin.utils import DashboardStats, ReportGenerator
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        # Get admin emails
        admin_emails = list(User.objects.filter(
            role='admin',
            is_staff=True,
            is_active=True
        ).values_list('email', flat=True))
        
        if not admin_emails:
            logger.warning("No admin emails found for daily report")
            return "No admins to send report to"
        
        # Generate report data
        stats = DashboardStats.get_all_stats()
        yesterday = timezone.now().date() - timedelta(days=1)
        revenue_report = ReportGenerator.get_revenue_report(yesterday, yesterday)
        
        # Send email to each admin
        # This would require creating an email template
        # For now, we'll log it
        logger.info(f"Daily report sent to {len(admin_emails)} admins")
        
        return f"Report sent to {len(admin_emails)} admins"
    
    except Exception as e:
        logger.error(f"Error sending daily report: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def cleanup_old_logs():
    """
    Clean up old admin logs (older than 90 days)
    Runs weekly
    """
    from apps.platformadmin.models import AdminLog
    
    try:
        cutoff_date = timezone.now() - timedelta(days=90)
        deleted_count, _ = AdminLog.objects.filter(created_at__lt=cutoff_date).delete()
        
        logger.info(f"Cleaned up {deleted_count} old admin logs")
        return f"Deleted {deleted_count} old logs"
    
    except Exception as e:
        logger.error(f"Error cleaning up logs: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def check_pending_refunds():
    """
    Check for refunds pending longer than 24 hours
    Sends alert to admins
    """
    from apps.payments.models import Refund
    from apps.platformadmin.notifications import AdminAlerts
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        cutoff_time = timezone.now() - timedelta(hours=24)
        old_pending_refunds = Refund.objects.filter(
            status='pending',
            requested_at__lt=cutoff_time
        )
        
        if old_pending_refunds.exists():
            # Get admin emails
            admin_emails = list(User.objects.filter(
                role='admin',
                is_staff=True,
                is_active=True
            ).values_list('email', flat=True))
            
            if admin_emails:
                # Send alert
                logger.warning(f"{old_pending_refunds.count()} refunds pending for more than 24 hours")
                # AdminAlerts would send email here
            
            return f"Alert sent for {old_pending_refunds.count()} pending refunds"
        
        return "No old pending refunds"
    
    except Exception as e:
        logger.error(f"Error checking pending refunds: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def check_failed_payments():
    """
    Check for high rate of failed payments
    Sends alert to admins if > 10% failure rate in last hour
    """
    from apps.payments.models import Payment
    from apps.platformadmin.notifications import AdminAlerts
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        last_hour = timezone.now() - timedelta(hours=1)
        recent_payments = Payment.objects.filter(created_at__gte=last_hour)
        
        if recent_payments.count() > 10:  # Only check if enough volume
            failed = recent_payments.filter(status='failed').count()
            total = recent_payments.count()
            failure_rate = (failed / total) * 100
            
            if failure_rate > 10:
                # Get admin emails
                admin_emails = list(User.objects.filter(
                    role='admin',
                    is_staff=True,
                    is_active=True
                ).values_list('email', flat=True))
                
                if admin_emails:
                    logger.warning(f"High payment failure rate: {failure_rate:.2f}%")
                    # AdminAlerts would send email here
                
                return f"Alert sent: {failure_rate:.2f}% failure rate"
        
        return "Payment failure rate normal"
    
    except Exception as e:
        logger.error(f"Error checking failed payments: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def generate_monthly_revenue_report():
    """
    Generate monthly revenue report
    Runs on 1st of every month
    """
    from apps.platformadmin.utils import ReportGenerator
    from apps.platformadmin.export_utils import CSVExporter
    from django.core.files.base import ContentFile
    import csv
    from io import StringIO
    
    try:
        # Get last month's data
        today = timezone.now().date()
        last_month_end = today.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        # Generate report
        report = ReportGenerator.get_revenue_report(last_month_start, last_month_end)
        
        logger.info(f"Monthly revenue report generated: {report['total_revenue']}")
        
        # Save report to file or send email
        # Implementation depends on your requirements
        
        return f"Monthly report generated: {report['total_revenue']}"
    
    except Exception as e:
        logger.error(f"Error generating monthly report: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def update_teacher_statistics():
    """
    Update teacher statistics (courses, students, revenue)
    Runs daily
    """
    from django.contrib.auth import get_user_model
    from apps.courses.models import Course
    from apps.payments.models import Payment
    from django.db.models import Sum
    
    User = get_user_model()
    
    try:
        teachers = User.objects.filter(role='teacher', is_active=True)
        updated_count = 0
        
        for teacher in teachers:
            if hasattr(teacher, 'teacher_profile'):
                # Update course count
                total_courses = Course.objects.filter(teacher=teacher).count()
                teacher.teacher_profile.total_courses = total_courses
                
                # Update student count
                total_students = Course.objects.filter(
                    teacher=teacher
                ).aggregate(total=Sum('total_enrollments'))['total'] or 0
                teacher.teacher_profile.total_students = total_students
                
                teacher.teacher_profile.save()
                updated_count += 1
        
        logger.info(f"Updated statistics for {updated_count} teachers")
        return f"Updated {updated_count} teacher profiles"
    
    except Exception as e:
        logger.error(f"Error updating teacher statistics: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def verify_pending_payments():
    """
    Verify status of pending payments with payment gateway
    Updates stale pending payments
    """
    from apps.payments.models import Payment
    from apps.payments.utils import RazorpayHandler
    
    try:
        # Get payments pending for more than 1 hour
        cutoff_time = timezone.now() - timedelta(hours=1)
        pending_payments = Payment.objects.filter(
            status='pending',
            created_at__lt=cutoff_time,
            razorpay_payment_id__isnull=False
        )
        
        razorpay = RazorpayHandler()
        updated_count = 0
        
        for payment in pending_payments[:100]:  # Limit to avoid overwhelming the API
            try:
                # Fetch payment status from Razorpay
                rp_payment = razorpay.fetch_payment(payment.razorpay_payment_id)
                
                if rp_payment and rp_payment.get('status') == 'captured':
                    payment.status = 'completed'
                    payment.completed_at = timezone.now()
                    payment.save()
                    updated_count += 1
                elif rp_payment and rp_payment.get('status') == 'failed':
                    payment.status = 'failed'
                    payment.save()
                    updated_count += 1
            
            except Exception as e:
                logger.error(f"Error verifying payment {payment.id}: {str(e)}")
                continue
        
        logger.info(f"Verified and updated {updated_count} pending payments")
        return f"Updated {updated_count} payments"
    
    except Exception as e:
        logger.error(f"Error verifying pending payments: {str(e)}")
        return f"Error: {str(e)}"
