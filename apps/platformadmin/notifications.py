"""
Email notification system for admin actions
Sends emails to users when admins take actions
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


class AdminEmailNotifier:
    """Send email notifications for admin actions"""
    
    @staticmethod
    def send_email(subject, to_email, template_name, context):
        """
        Send HTML email with plain text fallback
        
        Args:
            subject: Email subject
            to_email: Recipient email or list of emails
            template_name: Template name (without extension)
            context: Template context dictionary
        
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Render HTML content
            html_content = render_to_string(f'platformadmin/emails/{template_name}.html', context)
            text_content = strip_tags(html_content)
            
            # Create email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email] if isinstance(to_email, str) else to_email
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            
            logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    @staticmethod
    def notify_user_activated(user, admin_user):
        """Notify user when their account is activated"""
        context = {
            'user': user,
            'admin': admin_user,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Your Account Has Been Activated',
            to_email=user.email,
            template_name='user_activated',
            context=context
        )
    
    @staticmethod
    def notify_user_deactivated(user, admin_user, reason=''):
        """Notify user when their account is deactivated"""
        context = {
            'user': user,
            'admin': admin_user,
            'reason': reason,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Your Account Has Been Deactivated',
            to_email=user.email,
            template_name='user_deactivated',
            context=context
        )
    
    @staticmethod
    def notify_teacher_verified(user, admin_user):
        """Notify teacher when they are verified"""
        context = {
            'user': user,
            'admin': admin_user,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Congratulations! You Are Now a Verified Teacher',
            to_email=user.email,
            template_name='teacher_verified',
            context=context
        )
    
    @staticmethod
    def notify_course_approved(course, admin_user, comments=''):
        """Notify teacher when their course is approved"""
        context = {
            'course': course,
            'teacher': course.teacher,
            'admin': admin_user,
            'comments': comments,
        }
        
        return AdminEmailNotifier.send_email(
            subject=f'Your Course "{course.title}" Has Been Approved',
            to_email=course.teacher.email,
            template_name='course_approved',
            context=context
        )
    
    @staticmethod
    def notify_course_rejected(course, admin_user, reason='', comments=''):
        """Notify teacher when their course is rejected"""
        context = {
            'course': course,
            'teacher': course.teacher,
            'admin': admin_user,
            'reason': reason,
            'comments': comments,
        }
        
        return AdminEmailNotifier.send_email(
            subject=f'Your Course "{course.title}" Requires Revisions',
            to_email=course.teacher.email,
            template_name='course_rejected',
            context=context
        )
    
    @staticmethod
    def notify_refund_processed(payment, refund, admin_user):
        """Notify user when their refund is processed"""
        context = {
            'payment': payment,
            'refund': refund,
            'user': payment.user,
            'admin': admin_user,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Your Refund Has Been Processed',
            to_email=payment.user.email,
            template_name='refund_processed',
            context=context
        )
    
    @staticmethod
    def notify_refund_rejected(payment, refund, admin_user, reason=''):
        """Notify user when their refund is rejected"""
        context = {
            'payment': payment,
            'refund': refund,
            'user': payment.user,
            'admin': admin_user,
            'reason': reason,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Refund Request Update',
            to_email=payment.user.email,
            template_name='refund_rejected',
            context=context
        )
    
    @staticmethod
    def notify_role_changed(user, old_role, new_role, admin_user, permissions=None, admin_notes=''):
        """Notify user when their role is changed"""
        context = {
            'user': user,
            'old_role': old_role,
            'new_role': new_role,
            'assigned_by': admin_user,
            'permissions': permissions or [],
            'admin_notes': admin_notes,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Your Account Role Has Been Updated',
            to_email=user.email,
            template_name='role_changed',
            context=context
        )
    
    @staticmethod
    def notify_user_suspended(user, admin_user, reason='', duration='', suspension_until=None, admin_notes=''):
        """Notify user when their account is suspended"""
        context = {
            'user': user,
            'admin': admin_user,
            'reason': reason,
            'duration': duration,
            'suspension_until': suspension_until,
            'admin_notes': admin_notes,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Your Account Has Been Suspended',
            to_email=user.email,
            template_name='user_suspended',
            context=context
        )
    
    @staticmethod
    def notify_course_featured(course, admin_user, featured_duration='', featured_until=None, admin_notes=''):
        """Notify teacher when their course is featured"""
        context = {
            'course': course,
            'teacher': course.teacher,
            'admin': admin_user,
            'featured_duration': featured_duration,
            'featured_until': featured_until,
            'admin_notes': admin_notes,
        }
        
        return AdminEmailNotifier.send_email(
            subject=f'🌟 Your Course "{course.title}" is Now Featured!',
            to_email=course.teacher.email,
            template_name='course_featured',
            context=context
        )
    
    @staticmethod
    def send_bulk_email(user_emails, subject, message, sender=None, action_required=False, deadline=None):
        """Send bulk email to multiple users"""
        context = {
            'message': message,
            'sender': sender,
            'action_required': action_required,
            'deadline': deadline,
        }
        
        success_count = 0
        for email in user_emails:
            try:
                # Add user-specific context if email corresponds to a user
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(email=email)
                    context['user'] = user
                except User.DoesNotExist:
                    context['user'] = type('obj', (object,), {'email': email, 'get_full_name': lambda: email})()
                
                sent = AdminEmailNotifier.send_email(
                    subject=subject,
                    to_email=email,
                    template_name='bulk_message',
                    context=context
                )
                if sent:
                    success_count += 1
            except Exception as e:
                logger.error(f"Error sending bulk email to {email}: {str(e)}")
                continue
        
        return success_count


class AdminAlerts:
    """Send alerts to admins for important events"""
    
    @staticmethod
    def alert_high_refund_rate(admin_emails, refund_stats):
        """Alert admins when refund rate is high"""
        context = {
            'refund_stats': refund_stats,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Alert: High Refund Rate Detected',
            to_email=admin_emails,
            template_name='admin_alert_high_refunds',
            context=context
        )
    
    @staticmethod
    def alert_suspicious_activity(admin_emails, activity_details):
        """Alert admins about suspicious activity"""
        context = {
            'activity': activity_details,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Security Alert: Suspicious Activity Detected',
            to_email=admin_emails,
            template_name='admin_alert_suspicious',
            context=context
        )
    
    @staticmethod
    def alert_failed_payments(admin_emails, failed_payments):
        """Alert admins about failed payments"""
        context = {
            'failed_payments': failed_payments,
        }
        
        return AdminEmailNotifier.send_email(
            subject='Alert: Multiple Payment Failures Detected',
            to_email=admin_emails,
            template_name='admin_alert_failed_payments',
            context=context
        )
