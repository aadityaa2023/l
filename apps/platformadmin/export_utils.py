"""
CSV Export utilities for platformadmin
Generates CSV exports for various data types
"""
import csv
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal


class CSVExporter:
    """Handle CSV export operations"""
    
    @staticmethod
    def export_users(queryset, filename=None):
        """Export users to CSV"""
        if not filename:
            filename = f'users_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Email', 'First Name', 'Last Name', 'Role', 'Phone',
            'Active', 'Email Verified', 'Date Joined', 'Last Login'
        ])
        
        for user in queryset:
            writer.writerow([
                user.email,
                user.first_name,
                user.last_name,
                user.role,
                user.phone,
                'Yes' if user.is_active else 'No',
                'Yes' if user.email_verified else 'No',
                user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else '',
                user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else ''
            ])
        
        return response
    
    @staticmethod
    def export_courses(queryset, filename=None):
        """Export courses to CSV"""
        if not filename:
            filename = f'courses_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Title', 'Teacher Email', 'Category', 'Price', 'Currency',
            'Status', 'Featured', 'Total Enrollments', 'Rating',
            'Created At', 'Updated At'
        ])
        
        for course in queryset.select_related('teacher', 'category'):
            writer.writerow([
                course.title,
                course.teacher.email,
                course.category.name if course.category else '',
                course.price,
                course.currency,
                course.status,
                'Yes' if course.is_featured else 'No',
                course.total_enrollments,
                course.average_rating,
                course.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                course.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    
    @staticmethod
    def export_payments(queryset, filename=None):
        """Export payments to CSV"""
        if not filename:
            filename = f'payments_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Payment ID', 'User Email', 'Course Title', 'Amount', 'Currency',
            'Status', 'Payment Method', 'Razorpay Order ID', 'Razorpay Payment ID',
            'Created At', 'Completed At'
        ])
        
        for payment in queryset.select_related('user', 'course'):
            writer.writerow([
                str(payment.id),
                payment.user.email,
                payment.course.title if payment.course else '',
                payment.amount,
                payment.currency,
                payment.status,
                payment.payment_method,
                payment.razorpay_order_id,
                payment.razorpay_payment_id,
                payment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                payment.completed_at.strftime('%Y-%m-%d %H:%M:%S') if payment.completed_at else ''
            ])
        
        return response
    
    @staticmethod
    def export_refunds(queryset, filename=None):
        """Export refunds to CSV"""
        if not filename:
            filename = f'refunds_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Refund ID', 'Payment ID', 'User Email', 'Amount', 'Status',
            'Reason', 'Processed By', 'Requested At', 'Processed At'
        ])
        
        for refund in queryset.select_related('payment', 'user', 'processed_by'):
            writer.writerow([
                str(refund.id),
                str(refund.payment.id),
                refund.user.email,
                refund.amount,
                refund.status,
                refund.get_reason_display(),
                refund.processed_by.email if refund.processed_by else '',
                refund.requested_at.strftime('%Y-%m-%d %H:%M:%S'),
                refund.processed_at.strftime('%Y-%m-%d %H:%M:%S') if refund.processed_at else ''
            ])
        
        return response
    
    @staticmethod
    def export_admin_logs(queryset, filename=None):
        """Export admin activity logs to CSV"""
        if not filename:
            filename = f'admin_logs_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Log ID', 'Admin Email', 'Action', 'Content Type', 'Object ID',
            'Object Repr', 'Reason', 'IP Address', 'Created At'
        ])
        
        for log in queryset.select_related('admin'):
            writer.writerow([
                str(log.id),
                log.admin.email,
                log.get_action_display(),
                log.content_type,
                log.object_id,
                log.object_repr,
                log.reason,
                log.ip_address,
                log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    
    @staticmethod
    def export_enrollments(queryset, filename=None):
        """Export course enrollments to CSV"""
        if not filename:
            filename = f'enrollments_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Enrollment ID', 'Student Email', 'Course Title', 'Teacher Email',
            'Status', 'Progress', 'Enrolled At', 'Completed At'
        ])
        
        for enrollment in queryset.select_related('student', 'course', 'course__teacher'):
            writer.writerow([
                str(enrollment.id),
                enrollment.student.email,
                enrollment.course.title,
                enrollment.course.teacher.email,
                enrollment.status,
                f"{enrollment.progress_percentage}%" if hasattr(enrollment, 'progress_percentage') else '0%',
                enrollment.enrolled_at.strftime('%Y-%m-%d %H:%M:%S'),
                enrollment.completed_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(enrollment, 'completed_at') and enrollment.completed_at else ''
            ])
        
        return response
    
    @staticmethod
    def export_revenue_report(data, filename=None):
        """Export revenue report to CSV"""
        if not filename:
            filename = f'revenue_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Revenue', 'Transactions', 'Refunds', 'Net Revenue'])
        
        for row in data:
            writer.writerow([
                row.get('date', ''),
                row.get('revenue', 0),
                row.get('transactions', 0),
                row.get('refunds', 0),
                row.get('net_revenue', 0)
            ])
        
        return response
    
    @staticmethod
    def export_teacher_statistics(queryset, filename=None):
        """Export teacher statistics to CSV"""
        if not filename:
            filename = f'teacher_stats_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Teacher Email', 'Name', 'Verified', 'Total Courses', 'Published Courses',
            'Total Students', 'Total Revenue', 'Average Rating', 'Join Date'
        ])
        
        for teacher in queryset.select_related('teacher_profile'):
            total_courses = teacher.courses.count() if hasattr(teacher, 'courses') else 0
            published_courses = teacher.courses.filter(status='published').count() if hasattr(teacher, 'courses') else 0
            
            writer.writerow([
                teacher.email,
                teacher.get_full_name(),
                'Yes' if hasattr(teacher, 'teacher_profile') and teacher.teacher_profile.is_verified else 'No',
                total_courses,
                published_courses,
                teacher.teacher_profile.total_students if hasattr(teacher, 'teacher_profile') else 0,
                0,  # Calculate from payments
                teacher.teacher_profile.average_rating if hasattr(teacher, 'teacher_profile') else 0,
                teacher.date_joined.strftime('%Y-%m-%d')
            ])
        
        return response
