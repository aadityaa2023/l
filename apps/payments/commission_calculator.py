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
        - Commission is calculated ONLY on the final amount (after discount) according to the 
          commission percentage set by platform admin while assigning teacher to course
        - The discount is absorbed - nobody gets it as extra commission
        
        Example: 100 rupee course with 10% coupon and 30% platform commission:
        - User pays: 90 rupees (100 - 10% discount)
        - Platform commission: 27 rupees (30% of 90)
        - Teacher revenue: 63 rupees (70% of 90)
        - The 10 rupee discount is absorbed (nobody gets it)
        
        Returns:
            dict: {
                'platform_commission': Decimal,
                'teacher_revenue': Decimal,
                'commission_rate': Decimal,
                'scenario': str  # 'normal' or 'with_coupon'
            }
        """
        from apps.platformadmin.models import CourseAssignment
        
        final_amount = payment.amount  # Amount user actually paid (after discount)
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
        
        # Calculate commission on final_amount (amount user paid after discount)
        platform_commission = (final_amount * base_commission_rate) / 100
        teacher_revenue = final_amount - platform_commission
        
        # Initialize result
        result = {
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
