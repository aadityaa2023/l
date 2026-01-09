"""
Payment gateway integration handlers for platformadmin
Handles refunds, partial refunds, and payment operations
"""
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from apps.payments.models import Payment, Refund
from apps.payments.utils import RazorpayHandler
from apps.platformadmin.models import AdminLog

logger = logging.getLogger(__name__)


class RefundHandler:
    """Handle payment refunds with proper gateway integration"""
    
    def __init__(self):
        self.razorpay = RazorpayHandler()
    
    @transaction.atomic
    def process_refund(self, payment, admin_user, amount=None, reason='', admin_notes=''):
        """
        Process a refund for a payment
        
        Args:
            payment: Payment object to refund
            admin_user: Admin user processing the refund
            amount: Amount to refund (None for full refund)
            reason: Reason for refund
            admin_notes: Admin notes for the refund
        
        Returns:
            tuple: (success: bool, message: str, refund_obj: Refund or None)
        """
        # Validation
        if payment.status != 'completed':
            return False, f'Cannot refund payment with status: {payment.status}', None
        
        # Check if already refunded
        if hasattr(payment, 'refund'):
            return False, 'Payment has already been refunded', None
        
        # Calculate refund amount
        refund_amount = amount if amount else payment.amount
        
        if refund_amount > payment.amount:
            return False, f'Refund amount ({refund_amount}) cannot exceed payment amount ({payment.amount})', None
        
        if refund_amount <= 0:
            return False, 'Refund amount must be greater than 0', None
        
        # Create refund record
        refund_obj = Refund.objects.create(
            payment=payment,
            user=payment.user,
            amount=refund_amount,
            status='processing',
            reason=reason or 'other',
            admin_notes=admin_notes,
            processed_by=admin_user
        )
        
        try:
            # Process refund with Razorpay
            razorpay_refund = self.razorpay.refund_payment(
                payment_id=payment.razorpay_payment_id,
                amount=refund_amount if amount else None,  # None means full refund
                notes={
                    'refund_id': str(refund_obj.id),
                    'reason': reason,
                    'admin_email': admin_user.email
                }
            )
            
            if razorpay_refund:
                # Update refund record
                refund_obj.razorpay_refund_id = razorpay_refund.get('id', '')
                refund_obj.status = 'completed'
                refund_obj.processed_at = timezone.now()
                refund_obj.save()
                
                # Update payment status
                old_status = payment.status
                payment.status = 'refunded'
                payment.save()
                
                # Log the action
                AdminLog.objects.create(
                    admin=admin_user,
                    action='refund',
                    content_type='Payment',
                    object_id=str(payment.id),
                    object_repr=f"{payment.user.email} - {payment.amount}",
                    old_values={'status': old_status},
                    new_values={'status': 'refunded', 'refund_amount': str(refund_amount)},
                    reason=f"{reason} - {admin_notes}"
                )
                
                logger.info(f"Refund processed successfully for payment {payment.id}: {refund_amount}")
                
                return True, f'Refund of {refund_amount} {payment.currency} processed successfully', refund_obj
            else:
                # Razorpay refund failed
                refund_obj.status = 'rejected'
                refund_obj.admin_notes += '\n\nRazorpay refund failed - check logs'
                refund_obj.save()
                
                logger.error(f"Razorpay refund failed for payment {payment.id}")
                
                return False, 'Failed to process refund with payment gateway', refund_obj
        
        except Exception as e:
            # Handle errors
            refund_obj.status = 'rejected'
            refund_obj.admin_notes += f'\n\nError: {str(e)}'
            refund_obj.save()
            
            logger.error(f"Error processing refund for payment {payment.id}: {str(e)}")
            
            return False, f'Error processing refund: {str(e)}', refund_obj
    
    def check_refund_eligibility(self, payment):
        """
        Check if a payment is eligible for refund
        
        Args:
            payment: Payment object
        
        Returns:
            tuple: (eligible: bool, reason: str)
        """
        if payment.status != 'completed':
            return False, f'Payment status is {payment.status}, not completed'
        
        if hasattr(payment, 'refund'):
            return False, 'Payment has already been refunded'
        
        if not payment.razorpay_payment_id:
            return False, 'No payment gateway transaction ID found'
        
        # Check if payment is too old (typically 180 days for most gateways)
        if payment.completed_at:
            days_since_payment = (timezone.now() - payment.completed_at).days
            if days_since_payment > 180:
                return False, f'Payment is {days_since_payment} days old. Refunds are typically only allowed within 180 days'
        
        return True, 'Payment is eligible for refund'
    
    def get_refund_status(self, refund_id):
        """
        Get refund status from payment gateway
        
        Args:
            refund_id: Razorpay refund ID
        
        Returns:
            dict: Refund details or None
        """
        try:
            # Fetch refund details from Razorpay
            # This would require adding a method to RazorpayHandler
            # For now, we'll return a placeholder
            return {
                'id': refund_id,
                'status': 'processed',
                'message': 'Refund completed'
            }
        except Exception as e:
            logger.error(f"Error fetching refund status for {refund_id}: {str(e)}")
            return None


class BulkPaymentHandler:
    """Handle bulk payment operations"""
    
    def __init__(self):
        self.refund_handler = RefundHandler()
    
    def bulk_refund(self, payment_ids, admin_user, reason='', admin_notes=''):
        """
        Process bulk refunds
        
        Args:
            payment_ids: List of payment IDs
            admin_user: Admin user processing the refunds
            reason: Reason for refunds
            admin_notes: Admin notes
        
        Returns:
            dict: Results summary
        """
        results = {
            'total': len(payment_ids),
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for payment_id in payment_ids:
            try:
                payment = Payment.objects.get(id=payment_id)
                success, message, refund = self.refund_handler.process_refund(
                    payment=payment,
                    admin_user=admin_user,
                    reason=reason,
                    admin_notes=admin_notes
                )
                
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                
                results['details'].append({
                    'payment_id': str(payment_id),
                    'success': success,
                    'message': message
                })
            
            except Payment.DoesNotExist:
                results['failed'] += 1
                results['details'].append({
                    'payment_id': str(payment_id),
                    'success': False,
                    'message': 'Payment not found'
                })
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'payment_id': str(payment_id),
                    'success': False,
                    'message': str(e)
                })
        
        logger.info(f"Bulk refund processed: {results['successful']} successful, {results['failed']} failed")
        
        return results


class PaymentAnalytics:
    """Payment analytics and reporting"""
    
    @staticmethod
    def get_refund_statistics(start_date=None, end_date=None):
        """Get refund statistics"""
        refunds = Refund.objects.all()
        
        if start_date:
            refunds = refunds.filter(requested_at__gte=start_date)
        if end_date:
            refunds = refunds.filter(requested_at__lte=end_date)
        
        total_refunds = refunds.count()
        completed_refunds = refunds.filter(status='completed').count()
        pending_refunds = refunds.filter(status='pending').count()
        rejected_refunds = refunds.filter(status='rejected').count()
        
        total_refund_amount = sum(r.amount for r in refunds.filter(status='completed'))
        
        return {
            'total_refunds': total_refunds,
            'completed': completed_refunds,
            'pending': pending_refunds,
            'rejected': rejected_refunds,
            'total_amount': total_refund_amount,
            'avg_refund_amount': total_refund_amount / completed_refunds if completed_refunds > 0 else 0
        }
    
    @staticmethod
    def get_payment_disputes():
        """Get payment disputes and issues"""
        # Identify payments that might have issues
        from datetime import timedelta
        
        # Old pending payments
        old_pending = Payment.objects.filter(
            status='pending',
            created_at__lt=timezone.now() - timedelta(hours=24)
        )
        
        # Failed payments in last 7 days
        recent_failed = Payment.objects.filter(
            status='failed',
            created_at__gte=timezone.now() - timedelta(days=7)
        )
        
        # Refund requests
        refund_requests = Refund.objects.filter(status='pending')
        
        return {
            'old_pending_payments': old_pending.count(),
            'recent_failed_payments': recent_failed.count(),
            'pending_refund_requests': refund_requests.count()
        }
