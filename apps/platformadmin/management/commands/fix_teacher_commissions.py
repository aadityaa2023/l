"""
Management command to recalculate and fix teacher commission balances
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal
from apps.platformadmin.models import TeacherCommission, FreeUser
from apps.payments.models import Payment, CouponUsage
from apps.payments.commission_calculator import CommissionCalculator
from apps.users.models import User


class Command(BaseCommand):
    help = 'Recalculate and fix teacher commission balances to match actual payments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it',
        )
        parser.add_argument(
            '--teacher-email',
            type=str,
            help='Only fix commissions for a specific teacher (by email)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        teacher_email = options.get('teacher_email')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        # Get free user IDs to exclude
        free_user_ids = FreeUser.objects.filter(is_active=True).values_list('user_id', flat=True)

        # Get all teachers or specific teacher
        if teacher_email:
            teachers = User.objects.filter(role='teacher', email=teacher_email)
            if not teachers.exists():
                self.stdout.write(self.style.ERROR(f'Teacher with email {teacher_email} not found'))
                return
        else:
            teachers = User.objects.filter(role='teacher')

        self.stdout.write(f'\nProcessing {teachers.count()} teacher(s)...\n')

        total_fixed = 0
        total_discrepancies = 0

        for teacher in teachers:
            # Get all completed payments for this teacher's courses, excluding free users
            teacher_payments = Payment.objects.filter(
                course__teacher=teacher,
                status='completed'
            ).exclude(
                user_id__in=free_user_ids
            ).select_related('course')

            # Calculate actual earnings from payments
            actual_earnings = Decimal('0')
            for payment in teacher_payments:
                # Get coupon usage if any
                coupon_usage = CouponUsage.objects.filter(payment=payment).first()
                coupon = coupon_usage.coupon if coupon_usage else None

                # Calculate commission using the commission calculator
                commission_data = CommissionCalculator.calculate_commission(payment, coupon)
                actual_earnings += commission_data['teacher_revenue']

            # Get or create teacher commission record
            teacher_commission, created = TeacherCommission.objects.get_or_create(
                teacher=teacher
            )

            # Check for discrepancy
            old_total_earned = teacher_commission.total_earned
            old_remaining = teacher_commission.remaining_balance
            new_remaining = actual_earnings - teacher_commission.total_paid

            if old_total_earned != actual_earnings:
                total_discrepancies += 1
                discrepancy = actual_earnings - old_total_earned

                self.stdout.write(
                    self.style.WARNING(
                        f'\n{teacher.email}:'
                    )
                )
                self.stdout.write(f'  Old total_earned: ₹{old_total_earned}')
                self.stdout.write(f'  New total_earned: ₹{actual_earnings}')
                self.stdout.write(f'  Discrepancy: ₹{discrepancy}')
                self.stdout.write(f'  Total paid: ₹{teacher_commission.total_paid}')
                self.stdout.write(f'  Old remaining: ₹{old_remaining}')
                self.stdout.write(f'  New remaining: ₹{new_remaining}')

                if not dry_run:
                    teacher_commission.total_earned = actual_earnings
                    teacher_commission.save()
                    self.stdout.write(self.style.SUCCESS('  ✓ Fixed'))
                    total_fixed += 1
                else:
                    self.stdout.write(self.style.WARNING('  (Would fix in non-dry-run mode)'))
            else:
                self.stdout.write(f'{teacher.email}: OK (₹{actual_earnings})')

        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'Total teachers processed: {teachers.count()}')
        self.stdout.write(f'Discrepancies found: {total_discrepancies}')
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Teachers fixed: {total_fixed}'))
        else:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made'))
        self.stdout.write('='*60 + '\n')
