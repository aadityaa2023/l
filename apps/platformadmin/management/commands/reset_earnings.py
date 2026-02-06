"""
Management command to reset all earnings for platform admin and teachers.

Usage:
    python manage.py reset_earnings [--confirm]
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.platformadmin.models import (
    TeacherCommission,
    InstructorPayout,
    PayoutTransaction,
    ReferralProgram,
    Referral
)


class Command(BaseCommand):
    help = 'Reset all earnings for platform admin and teachers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm the reset action (required to actually perform the reset)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually resetting',
        )

    def handle(self, *args, **options):
        confirm = options.get('confirm')
        dry_run = options.get('dry_run')

        if not confirm and not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  WARNING: This will reset ALL earnings data!\n'
                    'This action cannot be undone.\n\n'
                    'To proceed, run:\n'
                    '  python manage.py reset_earnings --confirm\n\n'
                    'To see what would be reset without making changes:\n'
                    '  python manage.py reset_earnings --dry-run\n'
                )
            )
            return

        # Gather statistics before reset
        stats = self.gather_statistics()
        
        if dry_run:
            self.display_dry_run_info(stats)
            return

        # Proceed with actual reset
        self.stdout.write(self.style.WARNING('\n🔄 Starting earnings reset...\n'))
        
        try:
            with transaction.atomic():
                self.reset_earnings(stats)
                self.stdout.write(
                    self.style.SUCCESS('\n✅ Earnings reset completed successfully!\n')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error during reset: {str(e)}\n')
            )
            raise

    def gather_statistics(self):
        """Gather statistics about current earnings"""
        stats = {
            'teacher_commissions': {
                'count': 0,
                'total_earned': 0,
                'total_paid': 0,
                'remaining': 0,
            },
            'instructor_payouts': {
                'count': 0,
                'total_amount': 0,
                'pending': 0,
                'completed': 0,
            },
            'payout_transactions': {
                'count': 0,
                'total_amount': 0,
                'pending': 0,
                'completed': 0,
            },
            'referral_programs': {
                'count': 0,
                'total_earnings': 0,
            },
            'referrals': {
                'count': 0,
                'total_commission': 0,
            },
        }

        # Teacher Commissions
        teacher_commissions = TeacherCommission.objects.all()
        stats['teacher_commissions']['count'] = teacher_commissions.count()
        for tc in teacher_commissions:
            stats['teacher_commissions']['total_earned'] += tc.total_earned
            stats['teacher_commissions']['total_paid'] += tc.total_paid
            stats['teacher_commissions']['remaining'] += tc.remaining_balance

        # Instructor Payouts
        instructor_payouts = InstructorPayout.objects.all()
        stats['instructor_payouts']['count'] = instructor_payouts.count()
        stats['instructor_payouts']['pending'] = instructor_payouts.filter(status='pending').count()
        stats['instructor_payouts']['completed'] = instructor_payouts.filter(status='completed').count()
        for ip in instructor_payouts:
            stats['instructor_payouts']['total_amount'] += ip.net_amount

        # Payout Transactions
        payout_transactions = PayoutTransaction.objects.all()
        stats['payout_transactions']['count'] = payout_transactions.count()
        stats['payout_transactions']['pending'] = payout_transactions.filter(status='pending').count()
        stats['payout_transactions']['completed'] = payout_transactions.filter(status='completed').count()
        for pt in payout_transactions:
            stats['payout_transactions']['total_amount'] += pt.amount

        # Referral Programs
        referral_programs = ReferralProgram.objects.all()
        stats['referral_programs']['count'] = referral_programs.count()
        for rp in referral_programs:
            stats['referral_programs']['total_earnings'] += rp.total_earnings

        # Referrals
        referrals = Referral.objects.all()
        stats['referrals']['count'] = referrals.count()
        for r in referrals:
            stats['referrals']['total_commission'] += r.commission_earned

        return stats

    def display_dry_run_info(self, stats):
        """Display what would be reset in dry-run mode"""
        self.stdout.write(self.style.WARNING('\n📊 DRY RUN - No changes will be made\n'))
        self.stdout.write(self.style.WARNING('=' * 60))
        
        self.stdout.write(f'\n📈 Teacher Commissions:')
        self.stdout.write(f'  - Records: {stats["teacher_commissions"]["count"]}')
        self.stdout.write(f'  - Total Earned: ₹{stats["teacher_commissions"]["total_earned"]:.2f}')
        self.stdout.write(f'  - Total Paid: ₹{stats["teacher_commissions"]["total_paid"]:.2f}')
        self.stdout.write(f'  - Remaining Balance: ₹{stats["teacher_commissions"]["remaining"]:.2f}')
        
        self.stdout.write(f'\n💰 Instructor Payouts:')
        self.stdout.write(f'  - Records: {stats["instructor_payouts"]["count"]}')
        self.stdout.write(f'  - Total Amount: ₹{stats["instructor_payouts"]["total_amount"]:.2f}')
        self.stdout.write(f'  - Pending: {stats["instructor_payouts"]["pending"]}')
        self.stdout.write(f'  - Completed: {stats["instructor_payouts"]["completed"]}')
        
        self.stdout.write(f'\n💳 Payout Transactions:')
        self.stdout.write(f'  - Records: {stats["payout_transactions"]["count"]}')
        self.stdout.write(f'  - Total Amount: ₹{stats["payout_transactions"]["total_amount"]:.2f}')
        self.stdout.write(f'  - Pending: {stats["payout_transactions"]["pending"]}')
        self.stdout.write(f'  - Completed: {stats["payout_transactions"]["completed"]}')
        
        self.stdout.write(f'\n🔗 Referral Programs:')
        self.stdout.write(f'  - Records: {stats["referral_programs"]["count"]}')
        self.stdout.write(f'  - Total Earnings: ₹{stats["referral_programs"]["total_earnings"]:.2f}')
        
        self.stdout.write(f'\n👥 Referrals:')
        self.stdout.write(f'  - Records: {stats["referrals"]["count"]}')
        self.stdout.write(f'  - Total Commission: ₹{stats["referrals"]["total_commission"]:.2f}')
        
        self.stdout.write(self.style.WARNING('\n' + '=' * 60))
        self.stdout.write(
            self.style.WARNING(
                '\nAll these values will be reset to 0 when running with --confirm\n'
            )
        )

    def reset_earnings(self, stats):
        """Perform the actual reset of earnings"""
        
        # 1. Reset Teacher Commissions
        self.stdout.write('Resetting teacher commissions...')
        updated = TeacherCommission.objects.update(
            total_earned=0,
            total_paid=0,
            last_payout_at=None
        )
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ Reset {updated} teacher commission records')
        )

        # 2. Delete or mark Instructor Payouts as cancelled
        self.stdout.write('Resetting instructor payouts...')
        # Option 1: Delete all records (uncomment if you want to delete)
        # deleted_count = InstructorPayout.objects.all().delete()[0]
        # self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted {deleted_count} instructor payout records'))
        
        # Option 2: Mark all as cancelled (keeping records for audit)
        updated = InstructorPayout.objects.exclude(status='cancelled').update(status='cancelled')
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ Cancelled {updated} instructor payout records')
        )

        # 3. Delete or mark Payout Transactions as cancelled
        self.stdout.write('Resetting payout transactions...')
        # Option 1: Delete all records (uncomment if you want to delete)
        # deleted_count = PayoutTransaction.objects.all().delete()[0]
        # self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted {deleted_count} payout transaction records'))
        
        # Option 2: Mark all as cancelled (keeping records for audit)
        updated = PayoutTransaction.objects.exclude(status='cancelled').update(status='cancelled')
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ Cancelled {updated} payout transaction records')
        )

        # 4. Reset Referral Program earnings
        self.stdout.write('Resetting referral program earnings...')
        updated = ReferralProgram.objects.update(
            total_referrals=0,
            successful_conversions=0,
            total_earnings=0
        )
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ Reset {updated} referral program records')
        )

        # 5. Reset individual referral commissions
        self.stdout.write('Resetting individual referral commissions...')
        updated = Referral.objects.update(
            commission_earned=0,
            status='pending',
            converted_payment=None,
            converted_at=None
        )
        self.stdout.write(
            self.style.SUCCESS(f'  ✓ Reset {updated} referral records')
        )

        # Display final statistics
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('Summary of Reset:'))
        self.stdout.write(f'  • Teacher Commissions: {stats["teacher_commissions"]["count"]} records')
        self.stdout.write(f'  • Instructor Payouts: {stats["instructor_payouts"]["count"]} records')
        self.stdout.write(f'  • Payout Transactions: {stats["payout_transactions"]["count"]} records')
        self.stdout.write(f'  • Referral Programs: {stats["referral_programs"]["count"]} records')
        self.stdout.write(f'  • Referrals: {stats["referrals"]["count"]} records')
        self.stdout.write('=' * 60)
