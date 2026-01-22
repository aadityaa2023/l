"""
Management command to populate TeacherCommission balances from existing payment data
Run this once after implementing the new payout system to backfill historical data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Sum
from apps.payments.models import Payment
from apps.platformadmin.models import TeacherCommission, CourseAssignment
from apps.payments.commission_calculator import CommissionCalculator
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate TeacherCommission balances from existing completed payments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Get all completed payments with courses
        completed_payments = Payment.objects.filter(
            status='completed',
            course__isnull=False
        ).select_related('course')
        
        self.stdout.write(f"Found {completed_payments.count()} completed payments with courses")
        
        # Track teachers and their earnings
        teacher_earnings = {}
        
        for payment in completed_payments:
            # Calculate commission for this payment
            commission_data = CommissionCalculator.calculate_commission(payment)
            teacher_revenue = commission_data.get('teacher_revenue', 0)
            
            # Get the teacher from course assignment or course
            teacher = None
            assignment = CommissionCalculator.get_teacher_assignment(payment.course)
            if assignment:
                teacher = assignment.teacher
            elif payment.course.teacher:
                teacher = payment.course.teacher
            
            if teacher and teacher_revenue > 0:
                if teacher.id not in teacher_earnings:
                    teacher_earnings[teacher.id] = {
                        'teacher': teacher,
                        'total_earned': Decimal('0.00'),
                        'payment_count': 0
                    }
                
                teacher_earnings[teacher.id]['total_earned'] += teacher_revenue
                teacher_earnings[teacher.id]['payment_count'] += 1
        
        # Create or update TeacherCommission records
        self.stdout.write(f"\nProcessing {len(teacher_earnings)} teachers...")
        
        created_count = 0
        updated_count = 0
        
        for teacher_id, data in teacher_earnings.items():
            teacher = data['teacher']
            total_earned = data['total_earned']
            payment_count = data['payment_count']
            
            if dry_run:
                self.stdout.write(
                    f"  Would create/update: {teacher.email} - "
                    f"₹{total_earned:,.2f} from {payment_count} payments"
                )
            else:
                # Get or create TeacherCommission
                commission, created = TeacherCommission.objects.get_or_create(
                    teacher=teacher,
                    defaults={
                        'total_earned': total_earned,
                        'total_paid': Decimal('0.00')
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ Created: {teacher.email} - "
                            f"₹{total_earned:,.2f} from {payment_count} payments"
                        )
                    )
                else:
                    # Update only if the calculated amount is different
                    if commission.total_earned != total_earned:
                        commission.total_earned = total_earned
                        commission.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Updated: {teacher.email} - "
                                f"₹{total_earned:,.2f} from {payment_count} payments"
                            )
                        )
                    else:
                        self.stdout.write(
                            f"  ○ No change: {teacher.email} - "
                            f"₹{total_earned:,.2f} from {payment_count} payments"
                        )
        
        # Summary
        self.stdout.write('\n' + '='*70)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would create {len(teacher_earnings)} commission records'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully processed teacher commissions:\n'
                    f'  - Created: {created_count}\n'
                    f'  - Updated: {updated_count}\n'
                    f'  - Total teachers: {len(teacher_earnings)}'
                )
            )
