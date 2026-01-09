"""
Razorpay payment integration utilities
"""
import razorpay
import hmac
import hashlib
from django.conf import settings
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class RazorpayHandler:
    """Handle Razorpay payment operations"""
    
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        self.client.set_app_details({
            "title": "Audio Learning Platform",
            "version": "1.0.0"
        })
    
    def create_order(self, amount, currency='INR', receipt=None, notes=None):
        """
        Create a Razorpay order
        
        Args:
            amount: Amount in smallest currency unit (paise for INR)
            currency: Currency code (default: INR)
            receipt: Receipt ID for reference
            notes: Dictionary of notes
        
        Returns:
            Order object or None on error
        """
        try:
            # Convert to paise (multiply by 100)
            amount_in_paise = int(Decimal(str(amount)) * 100)
            
            order_data = {
                'amount': amount_in_paise,
                'currency': currency,
                'receipt': receipt or '',
                'notes': notes or {}
            }
            
            order = self.client.order.create(data=order_data)
            logger.info(f"Razorpay order created: {order['id']}")
            return order
        
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {e}")
            return None
    
    def verify_payment_signature(self, razorpay_order_id, razorpay_payment_id, razorpay_signature):
        """
        Verify Razorpay payment signature
        
        Args:
            razorpay_order_id: Order ID
            razorpay_payment_id: Payment ID
            razorpay_signature: Signature to verify
        
        Returns:
            Boolean indicating if signature is valid
        """
        try:
            # Generate signature
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            generated_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = hmac.compare_digest(generated_signature, razorpay_signature)
            
            if is_valid:
                logger.info(f"Payment signature verified for order: {razorpay_order_id}")
            else:
                logger.warning(f"Invalid payment signature for order: {razorpay_order_id}")
            
            return is_valid
        
        except Exception as e:
            logger.error(f"Error verifying payment signature: {e}")
            return False
    
    def fetch_payment(self, payment_id):
        """
        Fetch payment details from Razorpay
        
        Args:
            payment_id: Razorpay payment ID
        
        Returns:
            Payment object or None
        """
        try:
            payment = self.client.payment.fetch(payment_id)
            return payment
        except Exception as e:
            logger.error(f"Error fetching payment {payment_id}: {e}")
            return None
    
    def capture_payment(self, payment_id, amount):
        """
        Capture a payment
        
        Args:
            payment_id: Payment ID to capture
            amount: Amount to capture in paise
        
        Returns:
            Payment object or None
        """
        try:
            amount_in_paise = int(Decimal(str(amount)) * 100)
            payment = self.client.payment.capture(payment_id, amount_in_paise)
            logger.info(f"Payment captured: {payment_id}")
            return payment
        except Exception as e:
            logger.error(f"Error capturing payment {payment_id}: {e}")
            return None
    
    def refund_payment(self, payment_id, amount=None, notes=None):
        """
        Create a refund for a payment
        
        Args:
            payment_id: Payment ID to refund
            amount: Amount to refund in paise (None for full refund)
            notes: Dictionary of notes
        
        Returns:
            Refund object or None
        """
        try:
            refund_data = {
                'notes': notes or {}
            }
            
            if amount:
                refund_data['amount'] = int(Decimal(str(amount)) * 100)
            
            refund = self.client.payment.refund(payment_id, refund_data)
            logger.info(f"Refund created for payment: {payment_id}")
            return refund
        
        except Exception as e:
            logger.error(f"Error creating refund for {payment_id}: {e}")
            return None
    
    def create_subscription(self, plan_id, customer_notify=1, total_count=None):
        """
        Create a subscription
        
        Args:
            plan_id: Razorpay plan ID
            customer_notify: Send notification to customer (1 or 0)
            total_count: Total billing cycles
        
        Returns:
            Subscription object or None
        """
        try:
            subscription_data = {
                'plan_id': plan_id,
                'customer_notify': customer_notify,
                'total_count': total_count or 12  # Default: 12 months
            }
            
            subscription = self.client.subscription.create(data=subscription_data)
            logger.info(f"Subscription created: {subscription['id']}")
            return subscription
        
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            return None
    
    def cancel_subscription(self, subscription_id):
        """
        Cancel a subscription
        
        Args:
            subscription_id: Subscription ID to cancel
        
        Returns:
            Subscription object or None
        """
        try:
            subscription = self.client.subscription.cancel(subscription_id)
            logger.info(f"Subscription cancelled: {subscription_id}")
            return subscription
        except Exception as e:
            logger.error(f"Error cancelling subscription {subscription_id}: {e}")
            return None
    
    def verify_webhook_signature(self, payload, signature):
        """
        Verify Razorpay webhook signature
        
        Args:
            payload: Request body (bytes)
            signature: X-Razorpay-Signature header value
        
        Returns:
            Boolean indicating if signature is valid
        """
        try:
            expected_signature = hmac.new(
                settings.RAZORPAY_WEBHOOK_SECRET.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if is_valid:
                logger.info("Webhook signature verified")
            else:
                logger.warning("Invalid webhook signature")
            
            return is_valid
        
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False


def convert_to_paise(amount):
    """
    Convert amount to paise (smallest currency unit for INR)
    
    Args:
        amount: Amount in rupees (Decimal or float)
    
    Returns:
        Amount in paise (integer)
    """
    return int(Decimal(str(amount)) * 100)


def convert_from_paise(amount_in_paise):
    """
    Convert amount from paise to rupees
    
    Args:
        amount_in_paise: Amount in paise (integer)
    
    Returns:
        Amount in rupees (Decimal)
    """
    return Decimal(str(amount_in_paise)) / 100


def create_razorpay_order(payment):
    """
    Create a Razorpay order for a payment
    
    Args:
        payment: Payment model instance
    
    Returns:
        Order dictionary from Razorpay
    """
    import time
    
    # Razorpay receipt has 40 char limit
    # Format: pay_<timestamp>_<short_id>
    # Example: pay_1703234567_abc123 (max 30 chars)
    timestamp = int(time.time())
    payment_short_id = str(payment.id)[:10]  # Take first 10 chars of UUID
    receipt = f'pay_{timestamp}_{payment_short_id}'
    
    handler = RazorpayHandler()
    order = handler.create_order(
        amount=payment.amount,
        currency=payment.currency,
        receipt=receipt,
        notes={
            'payment_id': str(payment.id),
            'course_id': str(payment.course.id),
            'course_title': payment.course.title[:100],  # Limit title length
            'user_id': str(payment.user.id),
            'user_email': payment.user.email,
        }
    )
    return order


def verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verify Razorpay payment signature
    
    Args:
        razorpay_order_id: Order ID
        razorpay_payment_id: Payment ID
        razorpay_signature: Signature to verify
    
    Returns:
        Boolean indicating if signature is valid
    """
    handler = RazorpayHandler()
    return handler.verify_payment_signature(
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature
    )


def fetch_and_validate_payment(razorpay_payment_id, expected_amount, expected_order_id):
    """
    Fetch payment from Razorpay and validate amount and order
    
    Args:
        razorpay_payment_id: Razorpay payment ID
        expected_amount: Expected amount in rupees (Decimal)
        expected_order_id: Expected Razorpay order ID
    
    Returns:
        Tuple (is_valid: bool, payment_details: dict or None, error_message: str or None)
    """
    try:
        handler = RazorpayHandler()
        payment_details = handler.fetch_payment(razorpay_payment_id)
        
        if not payment_details:
            return False, None, 'Failed to fetch payment details from Razorpay'
        
        # Validate payment status
        if payment_details.get('status') != 'captured':
            return False, payment_details, f"Payment status is {payment_details.get('status')}, expected 'captured'"
        
        # Validate order ID
        if payment_details.get('order_id') != expected_order_id:
            return False, payment_details, 'Order ID mismatch'
        
        # Validate amount (convert expected amount to paise)
        expected_amount_paise = convert_to_paise(expected_amount)
        actual_amount_paise = payment_details.get('amount', 0)
        
        if actual_amount_paise != expected_amount_paise:
            return False, payment_details, f'Amount mismatch: expected {expected_amount_paise} paise, got {actual_amount_paise} paise'
        
        logger.info(f'Payment validation successful: {razorpay_payment_id}')
        return True, payment_details, None
        
    except Exception as e:
        logger.error(f'Error validating payment {razorpay_payment_id}: {e}')
        return False, None, str(e)
