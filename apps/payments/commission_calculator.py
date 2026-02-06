"""
Commission calculation utilities for payment distribution
Handles revenue split between platform and teachers based on purchase scenarios
"""
from decimal import Decimal
from django.db.models import Q


class CommissionCalculator:
    """Calculate commission and revenue distribution for course purchases"""
    
    @staticmethod
    def get_teacher_assignment(course):
        """Get the teacher assignment for a course"""
        from apps.platformadmin.models import CourseAssignment
        
        assignment = CourseAssignment.objects.filter(
            course=course,
            status='accepted'
        ).first()
        
        return assignment
    
    @staticmethod
    def calculate_commission(payment, coupon_used=None):
        """
        Calculate commission distribution for a payment
        
        Commission Logic:
        - First, Razorpay fees (2% + 18% GST on fee) are deducted from gross amount
        - Commission is calculated ONLY on the net amount (after Razorpay fees and discount)
        - The discount is absorbed - nobody gets it as extra commission
        
        Example: 100 rupee payment with 30% platform commission:
        - User pays: ₹100 (gross amount)
        - Razorpay fee: ₹2.00 (2% of ₹100)
        - GST on fee: ₹0.36 (18% of ₹2.00)
        - Net amount: ₹97.64 (₹100 - ₹2.00 - ₹0.36)
        - Platform commission: ₹29.29 (30% of ₹97.64)
        - Teacher revenue: ₹68.35 (70% of ₹97.64)
        
        With coupon: 100 rupee course with 10% coupon and 30% platform commission:
        - User pays: ₹90 (100 - 10% discount)
        - Razorpay fee: ₹1.80 (2% of ₹90)
        - GST on fee: ₹0.32 (18% of ₹1.80)
        - Net amount: ₹87.88 (₹90 - ₹1.80 - ₹0.32)
        - Platform commission: ₹26.36 (30% of ₹87.88)
        - Teacher revenue: ₹61.52 (70% of ₹87.88)
        - The 10 rupee discount is absorbed (nobody gets it)
        
        Returns:
            dict: {
                'gross_amount': Decimal,
                'razorpay_fee': Decimal,
                'razorpay_gst': Decimal,
                'net_amount': Decimal,
                'platform_commission': Decimal,
                'teacher_revenue': Decimal,
                'commission_rate': Decimal,
                'scenario': str  # 'normal' or 'with_coupon'
            }
        """
        from apps.platformadmin.models import CourseAssignment
        from decimal import Decimal, ROUND_HALF_UP
        
        # Use net_amount if already calculated, otherwise use payment amount
        if payment.net_amount and payment.net_amount > 0:
            net_amount = payment.net_amount
            razorpay_fee = payment.razorpay_fee
            razorpay_gst = payment.razorpay_gst
        else:
            # Calculate fees if not already calculated
            fee_data = payment.calculate_and_set_fees()
            net_amount = fee_data['net_amount']
            razorpay_fee = fee_data['razorpay_fee']
            razorpay_gst = fee_data['razorpay_gst']
        
        gross_amount = payment.amount  # Amount user actually paid (after discount if any)
        course = payment.course
        
        # Get teacher assignment to get commission rate
        assignment = CourseAssignment.objects.filter(
            course=course,
            status__in=['assigned', 'accepted']
        ).first()
        
        # Default commission rate: use assignment value if present; otherwise
        # use platform setting `PLATFORM_DEFAULT_COMMISSION_PERCENTAGE` if set,
        # otherwise fallback to 0.00 (no hardcoded 30%).
        from django.conf import settings

        base_commission_rate = None
        if assignment and getattr(assignment, 'commission_percentage', None) is not None:
            base_commission_rate = assignment.commission_percentage
        else:
            platform_default = getattr(settings, 'PLATFORM_DEFAULT_COMMISSION_PERCENTAGE', None)
            if platform_default is not None:
                base_commission_rate = Decimal(str(platform_default))

        if base_commission_rate is None:
            base_commission_rate = Decimal('0.00')
        
        # Calculate commission on net_amount (after Razorpay fees deduction)
        platform_commission = (net_amount * base_commission_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        teacher_revenue = (net_amount - platform_commission).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Initialize result
        result = {
            'gross_amount': gross_amount,
            'razorpay_fee': razorpay_fee,
            'razorpay_gst': razorpay_gst,
            'net_amount': net_amount,
            'platform_commission': platform_commission,
            'teacher_revenue': teacher_revenue,
            'commission_rate': base_commission_rate,
            'scenario': 'with_coupon' if coupon_used else 'normal'
        }
        
        return result
    
    @staticmethod
    def record_commission_on_payment(payment, coupon_usage=None):
        """
        Record commission distribution on a completed payment
        
        Args:
            payment: Payment object
            coupon_usage: CouponUsage object if coupon was used (optional, not used in calculation)
        """
        coupon = coupon_usage.coupon if coupon_usage else None
        
        # Calculate commission based on final amount only
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        
        # Note: extra_commission_earned and commission_recipient in CouponUsage are 
        # legacy fields and not updated with new logic (discount is absorbed, not redistributed)
        
        # Store commission data in payment metadata (for future reference)
        # You could add a JSONField to Payment model to store this, or create a separate CommissionRecord model
        return commission_data
