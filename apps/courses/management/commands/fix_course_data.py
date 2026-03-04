"""
Management command to fix course data integrity issues that could cause 500 errors
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.courses.models import Course, Lesson
import uuid


class Command(BaseCommand):
    help = 'Fix course data integrity issues that could cause 500 errors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-slugs',
            action='store_true',
            help='Fix lessons with missing slugs',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix_slugs = options['fix_slugs']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )

        # Check for lessons with missing slugs
        lessons_without_slugs = Lesson.objects.filter(slug__isnull=True) | Lesson.objects.filter(slug='')
        
        if lessons_without_slugs.exists():
            self.stdout.write(
                self.style.ERROR(f'Found {lessons_without_slugs.count()} lessons without slugs:')
            )
            
            for lesson in lessons_without_slugs:
                course_title = lesson.course.title if lesson.course else 'No Course'
                self.stdout.write(f'  - Lesson ID {lesson.id}: "{lesson.title}" (Course: {course_title})')
                
                if fix_slugs and not dry_run:
                    # Generate a unique slug
                    base_slug = slugify(lesson.title) or f'lesson-{lesson.id}'
                    slug = base_slug
                    counter = 1
                    
                    while Lesson.objects.filter(course=lesson.course, slug=slug).exclude(pk=lesson.pk).exists():
                        slug = f"{base_slug}-{counter}"
                        counter += 1
                    
                    lesson.slug = slug
                    lesson.save(update_fields=['slug'])
                    self.stdout.write(
                        self.style.SUCCESS(f'    Fixed: Set slug to "{slug}"')
                    )
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ All lessons have slugs')
            )

        # Check for courses with None categories that could cause issues
        courses_with_none_category = Course.objects.filter(category__isnull=True)
        
        if courses_with_none_category.exists():
            self.stdout.write(
                self.style.WARNING(f'Found {courses_with_none_category.count()} courses without categories:')
            )
            
            for course in courses_with_none_category:
                self.stdout.write(f'  - Course ID {course.id}: "{course.title}" (Slug: {course.slug})')
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ All courses have categories')
            )

        # Check for courses with missing or invalid slugs
        courses_with_bad_slugs = Course.objects.filter(slug__isnull=True) | Course.objects.filter(slug='')
        
        if courses_with_bad_slugs.exists():
            self.stdout.write(
                self.style.ERROR(f'Found {courses_with_bad_slugs.count()} courses with missing slugs:')
            )
            
            for course in courses_with_bad_slugs:
                self.stdout.write(f'  - Course ID {course.id}: "{course.title}"')
                
                if fix_slugs and not dry_run:
                    # Generate a unique slug
                    base_slug = slugify(course.title) + '-' + str(uuid.uuid4())[:8]
                    course.slug = base_slug
                    course.save(update_fields=['slug'])
                    self.stdout.write(
                        self.style.SUCCESS(f'    Fixed: Set slug to "{base_slug}"')
                    )
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ All courses have slugs')
            )

        if fix_slugs and not dry_run:
            self.stdout.write(
                self.style.SUCCESS('Data integrity fixes completed!')
            )
        elif fix_slugs and dry_run:
            self.stdout.write(
                self.style.WARNING('Run without --dry-run to apply fixes')
            )

        self.stdout.write(
            self.style.SUCCESS('\nRecommendations:')
        )
        self.stdout.write('1. Run this command on production to check for data integrity issues')
        self.stdout.write('2. Use --fix-slugs to fix missing slug issues')
        self.stdout.write('3. Monitor Django logs for 500 errors and investigate further')