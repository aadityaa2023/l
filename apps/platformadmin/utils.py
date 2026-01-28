"""
Utility functions for platformadmin
"""
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from apps.courses.models import Course
from apps.payments.models import Payment
from apps.platformadmin.models import DashboardStat, AdminLog, CourseApproval
import json

User = get_user_model()


def get_platform_earnings():
    """Calculate platform earnings from completed payments"""
    from apps.payments.commission_calculator import CommissionCalculator
    from apps.payments.models import CouponUsage
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)
    
    # Get all completed payments
    completed_payments = Payment.objects.filter(status='completed')
    
    def calculate_earnings_for_period(payments_qs):
        """Calculate total platform earnings for a payment queryset"""
        total_earnings = Decimal('0')
        
        for payment in payments_qs:
            # Check if coupon was used
            try:
                coupon_usage = CouponUsage.objects.get(payment=payment)
                coupon = coupon_usage.coupon
            except CouponUsage.DoesNotExist:
                coupon = None
            
            # Calculate commission
            commission_data = CommissionCalculator.calculate_commission(payment, coupon)
            total_earnings += commission_data['platform_commission']
        
        return total_earnings
    
    # Calculate earnings for different periods
    earnings = {
        'total': calculate_earnings_for_period(completed_payments),
        'yesterday': calculate_earnings_for_period(
            completed_payments.filter(
                completed_at__gte=yesterday_start,
                completed_at__lt=today_start
            )
        ),
        'last_week': calculate_earnings_for_period(
            completed_payments.filter(completed_at__gte=week_start)
        ),
        'last_month': calculate_earnings_for_period(
            completed_payments.filter(completed_at__gte=month_start)
        ),
    }
    
    return earnings


class DashboardStats:
    """Class to handle dashboard statistics"""
    
    @staticmethod
    def get_user_stats():
        """Get user-related statistics"""
        stats = {
            'total_users': User.objects.filter(is_active=True).count(),
            'total_teachers': User.objects.filter(role='teacher', is_active=True).count(),
            'total_students': User.objects.filter(role='student', is_active=True).count(),
            'new_users_today': User.objects.filter(
                is_active=True,
                date_joined__date=timezone.now().date()
            ).count(),
            'inactive_users': User.objects.filter(is_active=False).count(),
            'unverified_emails': User.objects.filter(email_verified=False).count(),
        }
        
        return stats
    
    @staticmethod
    def get_course_stats():
        """Get course-related statistics"""
        stats = {
            'total_courses': Course.objects.count(),
            'published_courses': Course.objects.filter(status='published').count(),
            'draft_courses': Course.objects.filter(status='draft').count(),
            'archived_courses': Course.objects.filter(status='archived').count(),
            'pending_approval': CourseApproval.objects.filter(status='pending').count(),
            'featured_courses': Course.objects.filter(is_featured=True, status='published').count(),
            'new_courses_today': Course.objects.filter(
                created_at__date=timezone.now().date()
            ).count(),
        }
        
        return stats
    
    @staticmethod
    def get_revenue_stats():
        """Get revenue-related statistics"""
        completed_payments = Payment.objects.filter(status='completed')
        
        stats = {
            'total_revenue': completed_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0'),
            'today_revenue': completed_payments.filter(
                completed_at__date=timezone.now().date()
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0'),
            'monthly_revenue': completed_payments.filter(
                completed_at__month=timezone.now().month,
                completed_at__year=timezone.now().year
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0'),
            'completed_transactions': completed_payments.count(),
            'pending_transactions': Payment.objects.filter(status='pending').count(),
            'failed_transactions': Payment.objects.filter(status='failed').count(),
            'refunded_amount': Payment.objects.filter(status='refunded').aggregate(Sum('amount'))['amount__sum'] or Decimal('0'),
        }
        
        return stats
    
    @staticmethod
    def get_enrollment_stats():
        """Get enrollment statistics"""
        from apps.courses.models import Enrollment
        
        stats = {
            'total_enrollments': Enrollment.objects.filter(status='active').count(),
            'completed_enrollments': Enrollment.objects.filter(status='completed').count(),
            'cancelled_enrollments': Enrollment.objects.filter(status='cancelled').count(),
            'new_enrollments_today': Enrollment.objects.filter(
                enrolled_at__date=timezone.now().date()
            ).count(),
        }
        
        return stats
    
    @staticmethod
    def get_all_stats():
        """Get all dashboard statistics combined"""
        return {
            'users': DashboardStats.get_user_stats(),
            'courses': DashboardStats.get_course_stats(),
            'revenue': DashboardStats.get_revenue_stats(),
            'enrollments': DashboardStats.get_enrollment_stats(),
        }


class ReportGenerator:
    """Generate various reports for admin"""
    
    @staticmethod
    def get_revenue_report(start_date=None, end_date=None, days=30):
        """Generate revenue report with enhanced metrics"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=days)
        if not end_date:
            end_date = timezone.now().date()
        
        payments = Payment.objects.filter(
            status='completed',
            completed_at__date__gte=start_date,
            completed_at__date__lte=end_date
        )
        
        daily_revenue = {}
        for payment in payments:
            date_str = payment.completed_at.date().isoformat()
            if date_str not in daily_revenue:
                daily_revenue[date_str] = Decimal('0')
            daily_revenue[date_str] += payment.amount
        
        # Calculate previous period for comparison
        prev_start = start_date - timedelta(days=days)
        prev_end = start_date - timedelta(days=1)
        prev_payments = Payment.objects.filter(
            status='completed',
            completed_at__date__gte=prev_start,
            completed_at__date__lte=prev_end
        )
        prev_total = prev_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        total_revenue = sum(daily_revenue.values())
        growth = ((total_revenue - prev_total) / prev_total * 100) if prev_total > 0 else 0
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_revenue': total_revenue,
            'daily_revenue': daily_revenue,
            'avg_daily_revenue': sum(daily_revenue.values()) / len(daily_revenue) if daily_revenue else Decimal('0'),
            'total_transactions': payments.count(),
            'prev_period_revenue': prev_total,
            'growth_percentage': float(growth),
            'max_daily_revenue': max(daily_revenue.values()) if daily_revenue else Decimal('0'),
            'min_daily_revenue': min(daily_revenue.values()) if daily_revenue else Decimal('0'),
        }
    
    @staticmethod
    def get_user_report(start_date=None, end_date=None, days=30):
        """Generate user growth report with enhanced metrics"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=days)
        if not end_date:
            end_date = timezone.now().date()
        
        users = User.objects.filter(
            date_joined__date__gte=start_date,
            date_joined__date__lte=end_date
        )
        
        daily_users = {}
        for user in users:
            date_str = user.date_joined.date().isoformat()
            if date_str not in daily_users:
                daily_users[date_str] = {'total': 0, 'teachers': 0, 'students': 0}
            daily_users[date_str]['total'] += 1
            if user.role == 'teacher':
                daily_users[date_str]['teachers'] += 1
            elif user.role == 'student':
                daily_users[date_str]['students'] += 1
        
        # Calculate previous period for comparison
        prev_start = start_date - timedelta(days=days)
        prev_end = start_date - timedelta(days=1)
        prev_users = User.objects.filter(
            date_joined__date__gte=prev_start,
            date_joined__date__lte=prev_end
        )
        prev_total = prev_users.count()
        
        total_new_users = users.count()
        growth = ((total_new_users - prev_total) / prev_total * 100) if prev_total > 0 else 0
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_new_users': total_new_users,
            'new_teachers': users.filter(role='teacher').count(),
            'new_students': users.filter(role='student').count(),
            'daily_users': daily_users,
            'prev_period_users': prev_total,
            'growth_percentage': float(growth),
            'avg_daily_users': total_new_users / days if days > 0 else 0,
        }
    
    @staticmethod
    def get_course_stats_report():
        """Generate course statistics report with enhanced metrics"""
        from apps.courses.models import Enrollment
        
        courses = Course.objects.all()
        
        # Top courses by enrollment
        top_courses = courses.annotate(
            enrollment_count=Count('enrollments')
        ).order_by('-enrollment_count')[:10]
        
        # Category distribution
        category_distribution = courses.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'total_courses': courses.count(),
            'by_status': {
                'draft': courses.filter(status='draft').count(),
                'published': courses.filter(status='published').count(),
                'archived': courses.filter(status='archived').count(),
            },
            'by_teacher': courses.values('teacher__email', 'teacher__first_name', 'teacher__last_name').annotate(count=Count('id')).order_by('-count')[:10],
            'featured': courses.filter(is_featured=True).count(),
            'avg_price': courses.aggregate(avg=Count('price'))['avg'],
            'top_courses': list(top_courses.values('id', 'title', 'enrollment_count')),
            'category_distribution': list(category_distribution),
            'total_enrollments': Enrollment.objects.count(),
            'active_enrollments': Enrollment.objects.filter(status='active').count(),
        }


class ActivityLog:
    """Log admin activities"""
    
    @staticmethod
    def log_action(admin, action, content_type, object_id, object_repr, old_values=None, new_values=None, reason=''):
        """Generic method to log any admin action"""
        AdminLog.objects.create(
            admin=admin,
            action=action,
            content_type=content_type,
            object_id=str(object_id),
            object_repr=object_repr,
            old_values=old_values or {},
            new_values=new_values or {},
            reason=reason,
        )
    
    @staticmethod
    def log_user_action(user, admin, action, old_values=None, new_values=None, reason=''):
        """Log user management action"""
        AdminLog.objects.create(
            admin=admin,
            action=action,
            content_type='User',
            object_id=str(user.id),
            object_repr=user.email,
            old_values=old_values or {},
            new_values=new_values or {},
            reason=reason,
        )
    
    @staticmethod
    def log_course_action(course, admin, action, old_values=None, new_values=None, reason=''):
        """Log course management action"""
        AdminLog.objects.create(
            admin=admin,
            action=action,
            content_type='Course',
            object_id=str(course.id),
            object_repr=course.title,
            old_values=old_values or {},
            new_values=new_values or {},
            reason=reason,
        )
    
    @staticmethod
    def log_payment_action(payment, admin, action, old_values=None, new_values=None, reason=''):
        """Log payment management action"""
        AdminLog.objects.create(
            admin=admin,
            action=action,
            content_type='Payment',
            object_id=str(payment.id),
            object_repr=f"{payment.user.email} - {payment.amount}",
            old_values=old_values or {},
            new_values=new_values or {},
            reason=reason,
        )
    
    @staticmethod
    def get_recent_logs(limit=20):
        """Get recent admin logs"""
        return AdminLog.objects.select_related('admin').order_by('-created_at')[:limit]


def get_context_data(request, **kwargs):
    """Get common context data for platformadmin views"""
    context = {
        'stats': DashboardStats.get_all_stats(),
        'recent_logs': ActivityLog.get_recent_logs(10),
        'is_platformadmin': request.user.role == 'admin' and request.user.is_staff,
    }
    context.update(kwargs)
    return context
