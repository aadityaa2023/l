from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid
from .encryption import encrypt_payment_data, decrypt_payment_data


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
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2, help_text="Gross amount paid by user")
    currency = models.CharField(_('currency'), max_length=3, default='INR')
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(_('payment method'), max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    
    # Razorpay Fee Breakdown
    razorpay_fee = models.DecimalField(_('Razorpay fee'), max_digits=10, decimal_places=2, default=0, 
                                       help_text="2% transaction fee charged by Razorpay")
    razorpay_gst = models.DecimalField(_('GST on Razorpay fee'), max_digits=10, decimal_places=2, default=0,
                                       help_text="18% GST on Razorpay transaction fee")
    net_amount = models.DecimalField(_('net amount'), max_digits=10, decimal_places=2, default=0,
                                     help_text="Amount after deducting Razorpay fee and GST (used for commission split)")
    
    # Razorpay Details
    razorpay_order_id = models.CharField(_('Razorpay order ID'), max_length=255, blank=True, unique=True)
    razorpay_payment_id = models.CharField(_('Razorpay payment ID'), max_length=255, blank=True)
    razorpay_signature = models.CharField(_('Razorpay signature'), max_length=500, blank=True)
    
    # Encrypted Payment Method Details (256-bit AES encryption)
    encrypted_card_last4 = models.CharField(_('encrypted card last 4 digits'), max_length=500, blank=True, 
                                           help_text="Encrypted last 4 digits of card")
    encrypted_card_type = models.CharField(_('encrypted card type'), max_length=500, blank=True,
                                          help_text="Encrypted card type (Visa, Mastercard, etc.)")
    encrypted_upi_id = models.CharField(_('encrypted UPI ID'), max_length=500, blank=True,
                                        help_text="Encrypted UPI ID")
    encrypted_wallet_name = models.CharField(_('encrypted wallet name'), max_length=500, blank=True,
                                            help_text="Encrypted wallet name")
    encrypted_bank_name = models.CharField(_('encrypted bank name'), max_length=500, blank=True,
                                          help_text="Encrypted bank name for netbanking")
    
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
    
    def calculate_and_set_fees(self):
        """
        Calculate Razorpay fees, GST, and net amount
        
        Fee Structure:
        - Razorpay transaction fee: 2% of gross amount
        - GST on Razorpay fee: 18% of the transaction fee
        - Net amount: Gross amount - (Razorpay fee + GST)
        
        Example for ₹100 payment:
        - Razorpay fee: ₹100 × 2% = ₹2.00
        - GST: ₹2.00 × 18% = ₹0.36
        - Net amount: ₹100 - ₹2.00 - ₹0.36 = ₹97.64
        """
        from decimal import Decimal, ROUND_HALF_UP
        
        # Convert amount to Decimal for precise calculation
        gross_amount = Decimal(str(self.amount))
        
        # Calculate Razorpay fee (2%)
        razorpay_fee_rate = Decimal('0.02')  # 2%
        razorpay_fee = (gross_amount * razorpay_fee_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Calculate GST on Razorpay fee (18%)
        gst_rate = Decimal('0.18')  # 18%
        razorpay_gst = (razorpay_fee * gst_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Calculate net amount
        net_amount = gross_amount - razorpay_fee - razorpay_gst
        net_amount = net_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Update fields
        self.razorpay_fee = razorpay_fee
        self.razorpay_gst = razorpay_gst
        self.net_amount = net_amount
        
        return {
            'gross_amount': gross_amount,
            'razorpay_fee': razorpay_fee,
            'razorpay_gst': razorpay_gst,
            'net_amount': net_amount
        }
    
    # Payment Method Encryption/Decryption Methods
    
    def set_card_details(self, last4=None, card_type=None):
        """
        Encrypt and store card details
        
        Args:
            last4: Last 4 digits of card
            card_type: Card type (Visa, Mastercard, etc.)
        """
        if last4:
            self.encrypted_card_last4 = encrypt_payment_data(str(last4))
        if card_type:
            self.encrypted_card_type = encrypt_payment_data(str(card_type))
    
    def get_card_details(self):
        """
        Decrypt and return card details
        
        Returns:
            Dictionary with card_last4 and card_type
        """
        return {
            'card_last4': decrypt_payment_data(self.encrypted_card_last4) if self.encrypted_card_last4 else None,
            'card_type': decrypt_payment_data(self.encrypted_card_type) if self.encrypted_card_type else None,
        }
    
    def set_upi_id(self, upi_id):
        """
        Encrypt and store UPI ID
        
        Args:
            upi_id: UPI ID
        """
        if upi_id:
            self.encrypted_upi_id = encrypt_payment_data(str(upi_id))
    
    def get_upi_id(self):
        """
        Decrypt and return UPI ID
        
        Returns:
            Decrypted UPI ID or None
        """
        return decrypt_payment_data(self.encrypted_upi_id) if self.encrypted_upi_id else None
    
    def set_wallet_name(self, wallet_name):
        """
        Encrypt and store wallet name
        
        Args:
            wallet_name: Wallet name
        """
        if wallet_name:
            self.encrypted_wallet_name = encrypt_payment_data(str(wallet_name))
    
    def get_wallet_name(self):
        """
        Decrypt and return wallet name
        
        Returns:
            Decrypted wallet name or None
        """
        return decrypt_payment_data(self.encrypted_wallet_name) if self.encrypted_wallet_name else None
    
    def set_bank_name(self, bank_name):
        """
        Encrypt and store bank name
        
        Args:
            bank_name: Bank name for netbanking
        """
        if bank_name:
            self.encrypted_bank_name = encrypt_payment_data(str(bank_name))
    
    def get_bank_name(self):
        """
        Decrypt and return bank name
        
        Returns:
            Decrypted bank name or None
        """
        return decrypt_payment_data(self.encrypted_bank_name) if self.encrypted_bank_name else None
    
    def get_masked_payment_info(self):
        """
        Get masked payment information for display
        
        Returns:
            String with masked payment info
        """
        if self.payment_method == 'card':
            details = self.get_card_details()
            if details['card_last4']:
                return f"{details['card_type'] or 'Card'} ending in {details['card_last4']}"
        elif self.payment_method == 'upi':
            upi_id = self.get_upi_id()
            if upi_id:
                # Mask UPI ID (show first 2 and last 2 chars)
                if len(upi_id) > 4:
                    return f"{upi_id[:2]}{'*' * (len(upi_id) - 4)}{upi_id[-2:]}"
                return upi_id
        elif self.payment_method == 'wallet':
            wallet = self.get_wallet_name()
            if wallet:
                return f"{wallet} Wallet"
        elif self.payment_method == 'netbanking':
            bank = self.get_bank_name()
            if bank:
                return f"{bank} Net Banking"
        
        return self.get_payment_method_display()


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
    
    # Creator and Assignment
    CREATOR_TYPE_CHOICES = (
        ('platform_admin', 'Platform Admin'),
        ('teacher', 'Teacher'),
    )
    
    creator_type = models.CharField(
        _('creator type'), 
        max_length=20, 
        choices=CREATOR_TYPE_CHOICES, 
        default='platform_admin',
        help_text="Who created/owns this coupon"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_coupons'
    )
    
    # For teacher coupons - which teacher owns/can use this coupon
    assigned_to_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_teacher_coupons',
        limit_choices_to={'role': 'teacher'},
        help_text="If this is a teacher coupon, which teacher it belongs to"
    )
    
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
    
    # Commission Tracking (extra commission equals coupon discount %)
    extra_commission_earned = models.DecimalField(
        _('extra commission earned'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Extra commission from using this coupon (equals coupon discount %)"
    )
    commission_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commission_from_coupons',
        help_text="Who receives the extra commission (Platform Admin or Teacher)"
    )
    
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

