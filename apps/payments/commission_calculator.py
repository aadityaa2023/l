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
        
        Returns:
            dict: {
                'platform_commission': Decimal,
                'teacher_revenue': Decimal,
                'extra_commission': Decimal,
                'extra_commission_recipient': User or None,
                'commission_rate': Decimal,
                'scenario': str  # 'normal', 'platform_coupon', or 'teacher_coupon'
            }
        """
        from apps.platformadmin.models import CourseAssignment
        from apps.payments.models import CouponUsage
        
        final_amount = payment.amount
        course = payment.course
        
        # Get teacher assignment to get commission rate
        # Changed from 'accepted' to 'assigned' to include assigned teachers
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
        
        # Initialize result
        result = {
            'platform_commission': Decimal('0'),
            'teacher_revenue': Decimal('0'),
            'extra_commission': Decimal('0'),
            'extra_commission_recipient': None,
            'commission_rate': base_commission_rate,
            'scenario': 'normal'
        }
        
        # Scenario 1: Normal Purchase (No Coupon)
        if not coupon_used:
            result['scenario'] = 'normal'
            result['platform_commission'] = (final_amount * base_commission_rate) / 100
            result['teacher_revenue'] = final_amount - result['platform_commission']
            return result
        
        # Check if coupon is Platform Admin or Teacher coupon
        is_platform_coupon = coupon_used.creator_type == 'platform_admin'
        is_teacher_coupon = coupon_used.creator_type == 'teacher'
        
        # Get the actual discount amount from CouponUsage record instead of recalculating
        # This fixes the bug where discount was calculated on already-discounted amount
        coupon_usage = CouponUsage.objects.filter(payment=payment, coupon=coupon_used).first()
        if coupon_usage:
            extra_commission_amount = coupon_usage.discount_amount
        else:
            # Fallback: calculate discount on final_amount (should not happen in normal flow)
            try:
                extra_commission_amount = coupon_used.calculate_discount(final_amount)
            except Exception:
                extra_commission_amount = Decimal('0')
        
        # Scenario 2: Platform Admin Coupon Used
        if is_platform_coupon and not coupon_used.assigned_to_teacher:
            result['scenario'] = 'platform_coupon'
            result['extra_commission'] = extra_commission_amount
            result['extra_commission_recipient'] = None  # Platform keeps extra commission
            
            # Split final_amount according to base commission, then add discount to platform
            platform_base = (final_amount * base_commission_rate) / 100
            result['platform_commission'] = platform_base + extra_commission_amount
            result['teacher_revenue'] = final_amount - platform_base
            
        # Scenario 3: Teacher Coupon Used
        elif is_teacher_coupon or (is_platform_coupon and coupon_used.assigned_to_teacher):
            result['scenario'] = 'teacher_coupon'
            result['extra_commission'] = extra_commission_amount
            result['extra_commission_recipient'] = coupon_used.assigned_to_teacher or course.teacher
            
            # Split final_amount according to base commission, then add discount to teacher
            platform_base = (final_amount * base_commission_rate) / 100
            result['platform_commission'] = platform_base
            result['teacher_revenue'] = (final_amount - platform_base) + extra_commission_amount
        
        else:
            # Fallback to normal purchase if coupon type unclear
            result['scenario'] = 'normal'
            result['platform_commission'] = (final_amount * base_commission_rate) / 100
            result['teacher_revenue'] = final_amount - result['platform_commission']
        
        return result
    
    @staticmethod
    def record_commission_on_payment(payment, coupon_usage=None):
        """
        Record commission distribution on a completed payment
        
        Args:
            payment: Payment object
            coupon_usage: CouponUsage object if coupon was used
        """
        coupon = None
        if coupon_usage:
            coupon = coupon_usage.coupon
        
        # Calculate commission
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        
        # Update coupon usage with extra commission if applicable
        if coupon_usage and commission_data['extra_commission'] > 0:
            coupon_usage.extra_commission_earned = commission_data['extra_commission']
            coupon_usage.commission_recipient = commission_data['extra_commission_recipient']
            coupon_usage.save()
        
        # Store commission data in payment metadata (for future reference)
        # You could add a JSONField to Payment model to store this, or create a separate CommissionRecord model
        return commission_data
