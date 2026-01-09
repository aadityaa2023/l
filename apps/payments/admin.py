from django.contrib import admin
from unfold.admin import ModelAdmin
from django.utils.translation import gettext_lazy as _
from .models import Payment, Subscription, Refund, PaymentWebhook, Coupon, CouponUsage

# All payment-related models are hidden from Django admin
# Superadmin uses /platformadmin/ for payment management

# @admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ('user', 'course', 'amount', 'currency', 'status', 'payment_method', 'created_at', 'completed_at')
    list_filter = ('status', 'payment_method', 'created_at', 'completed_at')
    search_fields = ('user__email', 'course__title', 'razorpay_order_id', 'razorpay_payment_id')
    readonly_fields = ('id', 'created_at', 'updated_at', 'completed_at', 'razorpay_signature')
    
    # Unfold customizations
    list_filter_submit = True
    list_fullwidth = True
    
    fieldsets = (
        (_('Basic Information'), {'fields': ('user', 'course', 'amount', 'currency')}),
        (_('Payment Details'), {'fields': ('status', 'payment_method', 'description')}),
        (_('Razorpay Details'), {'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature')}),
        (_('Additional Info'), {'fields': ('failure_reason', 'notes', 'ip_address', 'user_agent')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at', 'completed_at')}),
    )


# @admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ('user', 'course', 'status', 'interval', 'amount', 'start_date', 'next_billing_date', 'end_date')
    list_filter = ('status', 'interval', 'created_at')
    search_fields = ('user__email', 'course__title', 'razorpay_subscription_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Basic Information'), {'fields': ('user', 'course')}),
        (_('Subscription Details'), {'fields': ('status', 'interval', 'amount', 'currency')}),
        (_('Razorpay Details'), {'fields': ('razorpay_subscription_id', 'razorpay_plan_id')}),
        (_('Billing Dates'), {'fields': ('start_date', 'next_billing_date', 'end_date')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# @admin.register(Refund)
class RefundAdmin(ModelAdmin):
    list_display = ('payment', 'user', 'status', 'amount', 'reason', 'requested_at', 'processed_at')
    list_filter = ('status', 'reason', 'requested_at', 'processed_at')
    search_fields = ('payment__razorpay_payment_id', 'user__email', 'reason_description')
    readonly_fields = ('requested_at', 'processed_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Request Details'), {'fields': ('payment', 'user', 'amount', 'reason', 'reason_description')}),
        (_('Razorpay'), {'fields': ('razorpay_refund_id',)}),
        (_('Status'), {'fields': ('status', 'admin_notes', 'processed_by')}),
        (_('Timestamps'), {'fields': ('requested_at', 'processed_at')}),
    )


# @admin.register(PaymentWebhook)
class PaymentWebhookAdmin(ModelAdmin):
    list_display = ('event_type', 'razorpay_event_id', 'is_processed', 'received_at', 'processed_at')
    list_filter = ('event_type', 'is_processed', 'received_at')
    search_fields = ('razorpay_event_id', 'event_type')
    readonly_fields = ('received_at', 'processed_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Webhook Info'), {'fields': ('event_type', 'razorpay_event_id', 'payload')}),
        (_('Processing'), {'fields': ('is_processed', 'processing_error')}),
        (_('Timestamps'), {'fields': ('received_at', 'processed_at')}),
    )


# @admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'status', 'valid_from', 
                    'valid_until', 'current_uses', 'max_uses')
    list_filter = ('status', 'discount_type', 'created_at')
    search_fields = ('code', 'description')
    readonly_fields = ('current_uses', 'created_at', 'updated_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Basic Information'), {'fields': ('code', 'description', 'status')}),
        (_('Discount Details'), {'fields': ('discount_type', 'discount_value', 'max_discount_amount', 'min_purchase_amount')}),
        (_('Validity'), {'fields': ('valid_from', 'valid_until')}),
        (_('Usage Limits'), {'fields': ('max_uses', 'max_uses_per_user', 'current_uses')}),
        (_('Applicability'), {'fields': ('applicable_courses', 'applicable_categories')}),
        (_('Metadata'), {'fields': ('created_by', 'created_at', 'updated_at')}),
    )


# @admin.register(CouponUsage)
class CouponUsageAdmin(ModelAdmin):
    list_display = ('user', 'coupon', 'original_amount', 'discount_amount', 'final_amount', 'used_at')
    list_filter = ('used_at',)
    search_fields = ('user__email', 'coupon__code')
    readonly_fields = ('id', 'coupon', 'user', 'payment', 'original_amount', 
                       'discount_amount', 'final_amount', 'used_at')
    
    # Unfold customizations
    list_filter_submit = True
    
    fieldsets = (
        (_('Usage Details'), {'fields': ('coupon', 'user', 'payment')}),
        (_('Amounts'), {'fields': ('original_amount', 'discount_amount', 'final_amount')}),
        (_('Timestamp'), {'fields': ('used_at',)}),
    )
    
    def has_add_permission(self, request):
        return False

