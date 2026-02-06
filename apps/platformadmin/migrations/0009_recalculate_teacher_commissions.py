"""
Data migration to recalculate teacher commissions based on new net amount logic
This resets and recalculates all teacher commission balances
"""
from django.db import migrations
from decimal import Decimal, ROUND_HALF_UP


def recalculate_teacher_commissions(apps, schema_editor):
    """
    Reset and recalculate all teacher commissions based on net amounts
    with proper Razorpay fee deduction
    """
    TeacherCommission = apps.get_model('platformadmin', 'TeacherCommission')
    Payment = apps.get_model('payments', 'Payment')
    CourseAssignment = apps.get_model('platformadmin', 'CourseAssignment')
    
    # First, reset all teacher commission totals to zero
    TeacherCommission.objects.all().update(total_earned=Decimal('0.00'))
    
    # Get all completed payments with courses
    completed_payments = Payment.objects.filter(
        status='completed',
        course__isnull=False
    ).select_related('course').order_by('completed_at')
    
    print(f"\nRecalculating commissions for {completed_payments.count()} completed payments...")
    
    for payment in completed_payments:
        # Ensure payment has net_amount calculated
        if not payment.net_amount or payment.net_amount == 0:
            continue
        
        # Get teacher from course
        teacher = None
        
        # Try to get teacher from CourseAssignment
        assignment = CourseAssignment.objects.filter(
            course=payment.course,
            status__in=['assigned', 'accepted']
        ).first()
        
        if assignment:
            teacher = assignment.teacher
        elif hasattr(payment.course, 'teacher'):
            teacher = payment.course.teacher
        
        if not teacher:
            continue
        
        # Get commission rate
        commission_rate = Decimal('0.00')
        if assignment and hasattr(assignment, 'commission_percentage'):
            commission_rate = assignment.commission_percentage
        
        # Calculate teacher's share of net amount
        net_amount = payment.net_amount
        platform_commission = (net_amount * commission_rate / 100).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        teacher_revenue = (net_amount - platform_commission).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        if teacher_revenue > 0:
            # Get or create TeacherCommission record
            commission, created = TeacherCommission.objects.get_or_create(
                teacher=teacher
            )
            
            # Add to total earned
            commission.total_earned += teacher_revenue
            commission.save()
            
            print(f"  Payment {payment.id}: Net ₹{net_amount} -> Teacher ₹{teacher_revenue} "
                  f"(Commission: {commission_rate}%)")
    
    # Show final balances
    print("\n" + "="*70)
    print("Final Teacher Commission Balances:")
    print("="*70)
    for tc in TeacherCommission.objects.all():
        print(f"  {tc.teacher.email}: ₹{tc.total_earned} earned, "
              f"₹{tc.total_paid} paid, ₹{tc.total_earned - tc.total_paid} remaining")
    print("="*70 + "\n")


def reverse_migration(apps, schema_editor):
    """
    Reverse by resetting all commissions to zero
    (We can't restore old incorrect values)
    """
    TeacherCommission = apps.get_model('platformadmin', 'TeacherCommission')
    TeacherCommission.objects.all().update(total_earned=Decimal('0.00'))


class Migration(migrations.Migration):

    dependencies = [
        ('platformadmin', '0008_freeuser'),
        ('payments', '0007_populate_razorpay_fees'),
    ]

    operations = [
        migrations.RunPython(
            recalculate_teacher_commissions,
            reverse_migration
        ),
    ]
