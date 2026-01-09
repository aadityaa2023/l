from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid


class Payment(models.Model):
    """Payment transactions"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('razorpay', 'Razorpay'),
        ('upi', 'UPI'),
        ('card', 'Credit/Debit Card'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Wallet'),
    )
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    course = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, null=True, related_name='payments')
    
    # Payment Details
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='INR')
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(_('payment method'), max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    
    # Razorpay Details
    razorpay_order_id = models.CharField(_('Razorpay order ID'), max_length=255, blank=True, unique=True)
    razorpay_payment_id = models.CharField(_('Razorpay payment ID'), max_length=255, blank=True)
    razorpay_signature = models.CharField(_('Razorpay signature'), max_length=500, blank=True)
    
    # Additional Info
    description = models.TextField(_('description'), blank=True)
    failure_reason = models.TextField(_('failure reason'), blank=True)
    notes = models.JSONField(_('notes'), default=dict, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.CharField(_('user agent'), max_length=500, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)

    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['razorpay_order_id']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.amount} {self.currency} ({self.status})"


class Subscription(models.Model):
    """Recurring subscription plans"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )
    
    INTERVAL_CHOICES = (
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    )
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='subscriptions')
    
    # Subscription Details
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='active')
    interval = models.CharField(_('billing interval'), max_length=20, choices=INTERVAL_CHOICES, default='monthly')
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='INR')
    
    # Razorpay Details
    razorpay_subscription_id = models.CharField(_('Razorpay subscription ID'), max_length=255, blank=True, unique=True)
    razorpay_plan_id = models.CharField(_('Razorpay plan ID'), max_length=255, blank=True)
    
    # Dates
    start_date = models.DateTimeField(_('start date'))
    next_billing_date = models.DateTimeField(_('next billing date'), null=True, blank=True)
    end_date = models.DateTimeField(_('end date'), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    cancelled_at = models.DateTimeField(_('cancelled at'), null=True, blank=True)

    class Meta:
        verbose_name = _('subscription')
        verbose_name_plural = _('subscriptions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['razorpay_subscription_id']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.course.title} ({self.status})"


class Refund(models.Model):
    """Refund requests and processing"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )
    
    REASON_CHOICES = (
        ('not_satisfied', 'Not Satisfied'),
        ('technical_issue', 'Technical Issue'),
        ('duplicate_payment', 'Duplicate Payment'),
        ('course_cancelled', 'Course Cancelled'),
        ('other', 'Other'),
    )
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='refund')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='refunds')
    
    # Refund Details
    amount = models.DecimalField(_('refund amount'), max_digits=10, decimal_places=2)
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.CharField(_('reason'), max_length=30, choices=REASON_CHOICES)
    reason_description = models.TextField(_('reason description'), blank=True)
    
    # Razorpay Details
    razorpay_refund_id = models.CharField(_('Razorpay refund ID'), max_length=255, blank=True)
    
    # Admin Notes
    admin_notes = models.TextField(_('admin notes'), blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds'
    )
    
    # Timestamps
    requested_at = models.DateTimeField(_('requested at'), auto_now_add=True)
    processed_at = models.DateTimeField(_('processed at'), null=True, blank=True)

    class Meta:
        verbose_name = _('refund')
        verbose_name_plural = _('refunds')
        ordering = ['-requested_at']

    def __str__(self):
        return f"Refund for {self.payment.id} - {self.amount} ({self.status})"


class PaymentWebhook(models.Model):
    """Store Razorpay webhook events for audit"""
    
    EVENT_CHOICES = (
        ('payment.authorized', 'Payment Authorized'),
        ('payment.captured', 'Payment Captured'),
        ('payment.failed', 'Payment Failed'),
        ('order.paid', 'Order Paid'),
        ('refund.created', 'Refund Created'),
        ('subscription.activated', 'Subscription Activated'),
        ('subscription.charged', 'Subscription Charged'),
        ('subscription.cancelled', 'Subscription Cancelled'),
        ('subscription.completed', 'Subscription Completed'),
        ('subscription.paused', 'Subscription Paused'),
        ('subscription.resumed', 'Subscription Resumed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(_('event type'), max_length=50, choices=EVENT_CHOICES)
    
    # Webhook Data
    razorpay_event_id = models.CharField(_('Razorpay event ID'), max_length=255, unique=True)
    payload = models.JSONField(_('payload'))
    
    # Processing
    is_processed = models.BooleanField(_('processed'), default=False)
    processing_error = models.TextField(_('processing error'), blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(_('received at'), auto_now_add=True)
    processed_at = models.DateTimeField(_('processed at'), null=True, blank=True)

    class Meta:
        verbose_name = _('payment webhook')
        verbose_name_plural = _('payment webhooks')
        ordering = ['-received_at']

    def __str__(self):
        return f"{self.event_type} - {self.razorpay_event_id}"


class Coupon(models.Model):
    """Discount coupons and promo codes"""
    
    DISCOUNT_TYPE_CHOICES = (
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
    )
    
    # Basic Information
    code = models.CharField(_('coupon code'), max_length=50, unique=True)
    description = models.TextField(_('description'), blank=True)
    
    # Discount Details
    discount_type = models.CharField(_('discount type'), max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(_('discount value'), max_digits=10, decimal_places=2)
    max_discount_amount = models.DecimalField(_('max discount amount'), max_digits=10, decimal_places=2, null=True, blank=True,
                                               help_text="Maximum discount for percentage type")
    min_purchase_amount = models.DecimalField(_('minimum purchase'), max_digits=10, decimal_places=2, default=0)
    
    # Validity
    valid_from = models.DateTimeField(_('valid from'))
    valid_until = models.DateTimeField(_('valid until'))
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Usage Limits
    max_uses = models.PositiveIntegerField(_('max uses'), null=True, blank=True, 
                                            help_text="Total uses allowed, null for unlimited")
    max_uses_per_user = models.PositiveIntegerField(_('max uses per user'), default=1)
    current_uses = models.PositiveIntegerField(_('current uses'), default=0)
    
    # Applicability
    applicable_courses = models.ManyToManyField('courses.Course', blank=True, related_name='coupons',
                                                 help_text="Leave empty for all courses")
    applicable_categories = models.ManyToManyField('courses.Category', blank=True, related_name='coupons',
                                                    help_text="Leave empty for all categories")
    
    # Created by
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_coupons')
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('coupon')
        verbose_name_plural = _('coupons')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.discount_value}{' %' if self.discount_type == 'percentage' else ''}"
    
    def is_valid(self):
        """Check if coupon is currently valid"""
        from django.utils import timezone
        now = timezone.now()
        
        if self.status != 'active':
            return False, "Coupon is not active"
        
        if now < self.valid_from:
            return False, "Coupon not yet valid"
        
        if now > self.valid_until:
            return False, "Coupon has expired"
        
        if self.max_uses and self.current_uses >= self.max_uses:
            return False, "Coupon usage limit reached"
        
        return True, "Valid"
    
    def calculate_discount(self, amount):
        """Calculate discount amount for given purchase amount"""
        if amount < self.min_purchase_amount:
            return 0
        
        if self.discount_type == 'percentage':
            discount = (amount * self.discount_value) / 100
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:
            discount = self.discount_value
        
        return min(discount, amount)  # Discount can't exceed purchase amount


class CouponUsage(models.Model):
    """Track coupon usage"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coupon_usages')
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='coupon_usage')
    
    # Discount Applied
    original_amount = models.DecimalField(_('original amount'), max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(_('discount amount'), max_digits=10, decimal_places=2)
    final_amount = models.DecimalField(_('final amount'), max_digits=10, decimal_places=2)
    
    # Metadata
    used_at = models.DateTimeField(_('used at'), auto_now_add=True)

    class Meta:
        verbose_name = _('coupon usage')
        verbose_name_plural = _('coupon usages')
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['coupon', '-used_at']),
            models.Index(fields=['user', '-used_at']),
        ]

    def __str__(self):
        return f"{self.user.email} used {self.coupon.code} - ₹{self.discount_amount}"

