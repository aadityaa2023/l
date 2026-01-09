"""
Utility functions for platformadmin
"""
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
from decimal import Decimal
from apps.courses.models import Course
from apps.payments.models import Payment
from apps.platformadmin.models import DashboardStat, AdminLog, CourseApproval
import json

User = get_user_model()


class DashboardStats:
    """Class to handle dashboard statistics"""
    
    @staticmethod
    def get_cache_key(stat_type):
        """Generate cache key for stats"""
        return f'dashboard_stats_{stat_type}_{timezone.now().date()}'
    
    @staticmethod
    def get_user_stats():
        """Get user-related statistics"""
        cache_key = DashboardStats.get_cache_key('users')
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
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
        
        # Cache for 1 hour
        cache.set(cache_key, stats, 3600)
        return stats
    
    @staticmethod
    def get_course_stats():
        """Get course-related statistics"""
        cache_key = DashboardStats.get_cache_key('courses')
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
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
        
        # Cache for 1 hour
        cache.set(cache_key, stats, 3600)
        return stats
    
    @staticmethod
    def get_revenue_stats():
        """Get revenue-related statistics"""
        cache_key = DashboardStats.get_cache_key('revenue')
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
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
        
        # Cache for 30 minutes
        cache.set(cache_key, stats, 1800)
        return stats
    
    @staticmethod
    def get_enrollment_stats():
        """Get enrollment statistics"""
        cache_key = DashboardStats.get_cache_key('enrollments')
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
        from apps.courses.models import Enrollment
        
        stats = {
            'total_enrollments': Enrollment.objects.filter(status='active').count(),
            'completed_enrollments': Enrollment.objects.filter(status='completed').count(),
            'cancelled_enrollments': Enrollment.objects.filter(status='cancelled').count(),
            'new_enrollments_today': Enrollment.objects.filter(
                enrolled_at__date=timezone.now().date()
            ).count(),
        }
        
        # Cache for 1 hour
        cache.set(cache_key, stats, 3600)
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
    
    @staticmethod
    def clear_cache():
        """Clear all cached statistics"""
        cache.delete_many([
            DashboardStats.get_cache_key('users'),
            DashboardStats.get_cache_key('courses'),
            DashboardStats.get_cache_key('revenue'),
            DashboardStats.get_cache_key('enrollments'),
        ])


class ReportGenerator:
    """Generate various reports for admin"""
    
    @staticmethod
    def get_revenue_report(start_date=None, end_date=None):
        """Generate revenue report"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
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
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_revenue': sum(daily_revenue.values()),
            'daily_revenue': daily_revenue,
            'avg_daily_revenue': sum(daily_revenue.values()) / len(daily_revenue) if daily_revenue else Decimal('0'),
        }
    
    @staticmethod
    def get_user_report(start_date=None, end_date=None):
        """Generate user growth report"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
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
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_new_users': users.count(),
            'new_teachers': users.filter(role='teacher').count(),
            'new_students': users.filter(role='student').count(),
            'daily_users': daily_users,
        }
    
    @staticmethod
    def get_course_stats_report():
        """Generate course statistics report"""
        return {
            'total_courses': Course.objects.count(),
            'by_status': {
                'draft': Course.objects.filter(status='draft').count(),
                'published': Course.objects.filter(status='published').count(),
                'archived': Course.objects.filter(status='archived').count(),
            },
            'by_teacher': Course.objects.values('teacher__email').annotate(count=Count('id')).order_by('-count')[:10],
            'featured': Course.objects.filter(is_featured=True).count(),
            'avg_price': Course.objects.aggregate(avg=Count('price'))['avg'],
        }


class ActivityLog:
    """Log admin activities"""
    
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
