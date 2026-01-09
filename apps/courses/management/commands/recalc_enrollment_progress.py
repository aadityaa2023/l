"""
Management command to recalculate progress for all enrollments.
Useful for syncing legacy data or fixing inconsistencies.

Usage:
    python manage.py recalc_enrollment_progress
    python manage.py recalc_enrollment_progress --course-id=1
    python manage.py recalc_enrollment_progress --student-email=user@example.com
"""
from django.core.management.base import BaseCommand, CommandError
from apps.courses.models import Enrollment
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Recalculate and update progress for enrollments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course-id',
            type=int,
            help='Recalculate only for a specific course ID',
        )
        parser.add_argument(
            '--student-email',
            type=str,
            help='Recalculate only for a specific student email',
        )
        parser.add_argument(
            '--enrollment-id',
            type=int,
            help='Recalculate only for a specific enrollment ID',
        )

    def handle(self, *args, **options):
        queryset = Enrollment.objects.all()
        
        # Filter by course if specified
        if options['course_id']:
            queryset = queryset.filter(course_id=options['course_id'])
            self.stdout.write(f"Filtering by course ID: {options['course_id']}")
        
        # Filter by student if specified
        if options['student_email']:
            try:
                student = User.objects.get(email=options['student_email'])
                queryset = queryset.filter(student=student)
                self.stdout.write(f"Filtering by student: {options['student_email']}")
            except User.DoesNotExist:
                raise CommandError(f"Student with email '{options['student_email']}' not found")
        
        # Filter by enrollment ID if specified
        if options['enrollment_id']:
            queryset = queryset.filter(id=options['enrollment_id'])
            self.stdout.write(f"Filtering by enrollment ID: {options['enrollment_id']}")
        
        total = queryset.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No enrollments found matching criteria'))
            return
        
        self.stdout.write(f"Recalculating progress for {total} enrollment(s)...")
        
        updated_count = 0
        error_count = 0
        
        for enrollment in queryset.select_related('course', 'student'):
            try:
                # Store old values for comparison
                old_progress = enrollment.progress_percentage
                old_completed = enrollment.lessons_completed
                
                # Recalculate
                enrollment.update_progress()
                
                # Show diff if changed
                if old_progress != enrollment.progress_percentage or old_completed != enrollment.lessons_completed:
                    self.stdout.write(
                        f"  Updated: {enrollment.student.email} - {enrollment.course.title}"
                    )
                    self.stdout.write(
                        f"    Progress: {old_progress}% → {enrollment.progress_percentage}%"
                    )
                    self.stdout.write(
                        f"    Completed Lessons: {old_completed} → {enrollment.lessons_completed}"
                    )
                
                updated_count += 1
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  Error updating enrollment {enrollment.id}: {str(e)}"
                    )
                )
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} enrollment(s)"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Failed to update {error_count} enrollment(s)"))
