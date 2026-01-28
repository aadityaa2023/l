"""
Course views for browsing, enrollment, and learning
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Count, Avg, Q, Sum, Max
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from datetime import datetime, timedelta
import os
import mimetypes
import uuid

from .models import (
    Category, Course, Module, Lesson, LessonMedia, Enrollment,
    LessonProgress, Note, Review, Announcement
)
from apps.analytics.models import ListeningSession, TeacherAnalytics
from apps.payments.models import Payment, CouponUsage
from apps.payments.commission_calculator import CommissionCalculator
from apps.common.query_optimization import get_optimized_course_queryset


# Course Browsing
class CourseListView(ListView):
    """List all published courses"""
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'
    paginate_by = 12
    
    def get_queryset(self):
        # Build filter dictionary from GET parameters
        filters = {
            'category': self.request.GET.get('category'),
            'search': self.request.GET.get('search'),
            'level': self.request.GET.get('level'),
            'price_range': self.request.GET.get('price'),
            'featured': self.request.GET.get('featured') == 'true',
        }
        
        # Remove None/empty values
        filters = {k: v for k, v in filters.items() if v}
        
        # Get sort parameter
        sort = self.request.GET.get('sort', '-created_at')
        
        # Get courses directly
        return get_optimized_course_queryset(
            filters=filters,
            order_by=sort
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get categories list
        context['categories'] = Category.objects.filter(is_active=True).order_by('display_order', 'name')
        
        return context


class CourseDetailView(DetailView):
    """Course detail page with comprehensive caching"""
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    
    def get_queryset(self):
        return Course.objects.select_related('teacher', 'category').prefetch_related(
            'modules__lessons',
            'modules__lessons__media_files'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        user = self.request.user
        
        # Check if user is enrolled
        if user.is_authenticated:
            is_enrolled = Enrollment.objects.filter(
                student=user,
                course=course,
                status='active'
            ).exists()
            
            context['is_enrolled'] = is_enrolled
        else:
            context['is_enrolled'] = False
        
        # Get reviews
        context['reviews'] = list(Review.objects.filter(course=course)
                        .select_related('student')
                        .order_by('-created_at')[:10])
        
        # Get course stats
        course_stats = _get_course_stats(course)
        
        context['total_students'] = course_stats['total_students']
        context['avg_rating'] = course_stats['avg_rating']
        
        # Get related courses
        context['related_courses'] = list(Course.objects.filter(
            category=course.category,
            status='published'
        ).exclude(id=course.id).annotate(
            student_count=Count('enrollments')
        )[:4])
        
        # Determine visible lessons for non-enrolled users: only allow free previews + first lesson
        # Build a set of lesson ids that should be visible without enrollment
        visible_lesson_ids = set()
        try:
            # Query modules ordered to find the first lesson in the course
            first_module = Module.objects.filter(course=course).order_by('order').prefetch_related('lessons').first()
            if first_module:
                first_lesson = first_module.lessons.order_by('order').first()
                if first_lesson:
                    visible_lesson_ids.add(first_lesson.id)
        except Exception:
            # fallback: no first lesson
            first_lesson = None

        # Add any lessons marked as free preview
        free_preview_ids = Lesson.objects.filter(module__course=course, is_free_preview=True).values_list('id', flat=True)
        visible_lesson_ids.update(list(free_preview_ids))

        context['visible_lesson_ids'] = visible_lesson_ids

        return context


def _get_course_stats(course):
    """Helper function to calculate course statistics"""
    total_students = Enrollment.objects.filter(
        course=course,
        status='active'
    ).count()
    
    avg_rating = Review.objects.filter(
        course=course
    ).aggregate(avg=Avg('rating'))['avg'] or 0
    
    return {
        'total_students': total_students,
        'avg_rating': avg_rating
    }


# Enrollment
@login_required
def enroll_course(request, course_id):
    """Enroll in a course"""
    course = get_object_or_404(Course, id=course_id, status='published')
    
    # Check if already enrolled
    existing_enrollment = Enrollment.objects.filter(
        student=request.user,
        course=course
    ).first()
    
    if existing_enrollment:
        if existing_enrollment.status == 'active':
            messages.info(request, 'You are already enrolled in this course!')
        else:
            existing_enrollment.status = 'active'
            existing_enrollment.save()
            messages.success(request, 'Enrollment reactivated successfully!')
    else:
        # For free courses, enroll directly
        if course.price == 0:
            Enrollment.objects.create(
                student=request.user,
                course=course
            )
            messages.success(request, 'Successfully enrolled in the course!')
        else:
            # For paid courses, redirect to payment
            messages.info(request, 'Please complete the payment to enroll.')
            return redirect('payments:course_payment', course_id=course.id)
    
    return redirect('courses:course_detail', slug=course.slug)


# Learning Interface
@login_required
def course_learn(request, course_id):
    """Main learning interface for enrolled students"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check enrollment - handle missing enrollment gracefully
    enrollment = Enrollment.objects.filter(
        student=request.user,
        course=course,
        status='active'
    ).first()

    if not enrollment:
        # Not enrolled: direct user to enroll or course detail with a friendly message
        if course.price == 0 or getattr(course, 'is_free', False):
            messages.info(request, 'This is a free course. Enrolling you now.')
            return redirect('courses:enroll_course', course_id=course.id)
        else:
            messages.info(request, 'Please enroll to access this course.')
            return redirect('courses:course_detail', slug=course.slug)
    
    # Get course modules and lessons
    modules = Module.objects.filter(course=course).prefetch_related(
        'lessons',
        'lessons__media_files'
    ).order_by('order')
    
    # Get user's progress
    completed_lessons = LessonProgress.objects.filter(
        enrollment=enrollment,
        is_completed=True
    ).values_list('lesson_id', flat=True)
    
    # Get current lesson (first incomplete or first lesson)
    current_lesson = None
    for module in modules:
        for lesson in module.lessons.all():
            if lesson.id not in completed_lessons:
                current_lesson = lesson
                break
        if current_lesson:
            break
    
    if not current_lesson and modules.exists():
        # All lessons completed, show first lesson
        current_lesson = modules.first().lessons.first()
    
    # Get notes for current lesson if exists
    notes = []
    if current_lesson:
        notes = Note.objects.filter(
            enrollment=enrollment,
            lesson=current_lesson
        ).order_by('-created_at')
    
    # Get previous and next lessons
    previous_lesson = None
    next_lesson = None
    if current_lesson:
        all_lessons = []
        for module in modules:
            all_lessons.extend(list(module.lessons.all()))
        
        try:
            current_index = all_lessons.index(current_lesson)
            if current_index > 0:
                previous_lesson = all_lessons[current_index - 1]
            if current_index < len(all_lessons) - 1:
                next_lesson = all_lessons[current_index + 1]
        except ValueError:
            pass
    
    context = {
        'course': course,
        'enrollment': enrollment,
        'modules': modules,
        'current_lesson': current_lesson,
        'completed_lessons': list(completed_lessons),
        'notes': notes,
        'previous_lesson': previous_lesson,
        'next_lesson': next_lesson,
    }
    
    return render(request, 'courses/course_learn.html', context)


def lesson_view(request, slug):
    """View a specific lesson"""
    lesson = get_object_or_404(Lesson.objects.prefetch_related('media_files'), slug=slug)
    course = lesson.module.course

    # Determine enrollment (if user is authenticated)
    enrollment = None
    is_enrolled = False
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(
            student=request.user,
            course=course,
            status='active'
        ).first()
        is_enrolled = bool(enrollment)

    # Determine first lesson in course to allow preview
    first_lesson = None
    try:
        first_module = Module.objects.filter(course=course).order_by('order').prefetch_related('lessons').first()
        if first_module:
            first_lesson = first_module.lessons.order_by('order').first()
    except Exception:
        first_lesson = None

    # Allow access if enrolled, or lesson is marked free preview, or lesson is first lesson
    if not (is_enrolled or lesson.is_free_preview or (first_lesson and lesson.id == first_lesson.id)):
        # If user is not authenticated, send them to login with next
        if not request.user.is_authenticated:
            messages.info(request, 'Please log in to access this lesson.')
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        # Otherwise, encourage enrollment and send to course detail
        messages.info(request, 'Please enroll to access this lesson.')
        return redirect('courses:course_detail', slug=course.slug)
    
    # Get or create lesson progress for enrolled users
    progress = None
    if enrollment:
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson
        )
    
    # Format resume time (only available for enrolled users with progress)
    if progress and getattr(progress, 'last_position_seconds', 0):
        minutes = progress.last_position_seconds // 60
        seconds = progress.last_position_seconds % 60
        resume_time = f"{minutes}:{seconds:02d}"
    else:
        resume_time = None
    
    # Get user's notes for this lesson (only if enrolled)
    notes = []
    if enrollment:
        notes = Note.objects.filter(
            enrollment=enrollment,
            lesson=lesson
        ).order_by('-created_at')
    
    # Get listening sessions for this lesson (only for authenticated users)
    if request.user.is_authenticated:
        sessions = ListeningSession.objects.filter(
            user=request.user,
            lesson=lesson
        ).order_by('-started_at')[:5]
    else:
        sessions = []
    
    # Get all media files for this lesson
    media_files = lesson.media_files.all().order_by('order')
    
    context = {
        'lesson': lesson,
        'course': course,
        'enrollment': enrollment,
        'progress': progress,
        'resume_time': resume_time,
        'notes': notes,
        'sessions': sessions,
        'media_files': media_files,
        'is_preview': not is_enrolled,
    }
    
    return render(request, 'courses/lesson_view.html', context)


@login_required
def mark_lesson_complete(request, slug):
    """Mark a lesson as complete"""
    if request.method == 'POST':
        lesson = get_object_or_404(Lesson, slug=slug)
        enrollment = get_object_or_404(
            Enrollment,
            student=request.user,
            course=lesson.module.course,
            status='active'
        )
        
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson
        )
        
        progress.completed = True
        progress.completed_at = datetime.now()
        progress.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False}, status=400)


def lesson_audio_player(request, slug):
    """Dedicated audio player view for lessons"""
    lesson = get_object_or_404(Lesson.objects.select_related('module__course'), slug=slug)
    course = lesson.module.course

    # Determine enrollment (if user is authenticated)
    enrollment = None
    is_enrolled = False
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(
            student=request.user,
            course=course,
            status='active'
        ).first()
        is_enrolled = bool(enrollment)

    # Allow preview for first lesson or free preview
    first_lesson = None
    try:
        first_module = Module.objects.filter(course=course).order_by('order').prefetch_related('lessons').first()
        if first_module:
            first_lesson = first_module.lessons.order_by('order').first()
    except Exception:
        first_lesson = None

    if not (is_enrolled or lesson.is_free_preview or (first_lesson and lesson.id == first_lesson.id)):
        if not request.user.is_authenticated:
            messages.info(request, 'Please log in to access this lesson.')
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        messages.info(request, 'Please enroll to access this lesson.')
        return redirect('courses:course_detail', slug=course.slug)
    
    progress = None
    if enrollment:
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson
        )
    
    # Select the best audio URL: prefer Lesson.audio_file, then media_files of type 'audio'
    audio_url = None
    try:
        if lesson.audio_file:
            audio_url = lesson.get_audio_url
        else:
            audio_media = lesson.media_files.filter(media_type='audio').order_by('order').first()
            if audio_media:
                audio_url = audio_media.get_media_url
    except Exception:
        audio_url = None

    context = {
        'lesson': lesson,
        'course': course,
        'enrollment': enrollment,
        'progress': progress,
        'audio_url': audio_url,
    }

    return render(request, 'lessons/audioplayer.html', context)


def lesson_video_player(request, slug):
    """Dedicated video player view for lessons"""
    lesson = get_object_or_404(Lesson.objects.select_related('module__course').prefetch_related('media_files'), slug=slug)
    course = lesson.module.course

    # Determine enrollment (if user is authenticated)
    enrollment = None
    is_enrolled = False
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(
            student=request.user,
            course=course,
            status='active'
        ).first()
        is_enrolled = bool(enrollment)

    # Allow preview for first lesson or free preview
    first_lesson = None
    try:
        first_module = Module.objects.filter(course=course).order_by('order').prefetch_related('lessons').first()
        if first_module:
            first_lesson = first_module.lessons.order_by('order').first()
    except Exception:
        first_lesson = None

    if not (is_enrolled or lesson.is_free_preview or (first_lesson and lesson.id == first_lesson.id)):
        if not request.user.is_authenticated:
            messages.info(request, 'Please log in to access this lesson.')
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        messages.info(request, 'Please enroll to access this lesson.')
        return redirect('courses:course_detail', slug=course.slug)
    
    progress = None
    if enrollment:
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson
        )
    
    # Select the best video URL from Lesson.media_files with media_type 'video'
    video_url = None
    try:
        video_media = lesson.media_files.filter(media_type='video').order_by('order').first()
        if video_media:
            video_url = video_media.get_media_url
            print(f"[Video Player] Found video for lesson '{lesson.title}': {video_url}")
        else:
            print(f"[Video Player] No video media found for lesson '{lesson.title}' (ID: {lesson.id})")
            # Check if there are any media files at all
            all_media = lesson.media_files.all()
            print(f"[Video Player] Total media files for lesson: {all_media.count()}")
            for media in all_media:
                print(f"  - Media ID {media.id}: {media.media_type} - {media.media_file.name if media.media_file else 'No file'}")
    except Exception as e:
        print(f"[Video Player] Error getting video URL: {e}")
        video_url = None

    context = {
        'lesson': lesson,
        'course': course,
        'enrollment': enrollment,
        'progress': progress,
        'video_url': video_url,
    }

    return render(request, 'lessons/videoplayer.html', context)


@login_required
def lesson_update_progress(request, slug):
    """Update lesson progress via AJAX"""
    if request.method == 'POST':
        import json
        
        lesson = get_object_or_404(Lesson, slug=slug)
        enrollment = get_object_or_404(
            Enrollment,
            student=request.user,
            course=lesson.module.course,
            status='active'
        )
        
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson
        )
        
        try:
            data = json.loads(request.body)
            watch_time = data.get('watchTime', 0)
            is_completed = data.get('isCompleted', False)
            
            # Update progress
            progress.last_position_seconds = watch_time
            if is_completed and not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = datetime.now()
            
            # Calculate completion percentage
            if lesson.duration_seconds > 0:
                progress.completion_percentage = min(100, (watch_time / lesson.duration_seconds) * 100)
            
            progress.save()
            
            # Update enrollment progress
            enrollment.update_progress()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False}, status=400)


# Notes
@login_required
def create_note(request, slug):
    """Create a note for a lesson"""
    if request.method == 'POST':
        lesson = get_object_or_404(Lesson, slug=slug)
        enrollment = get_object_or_404(
            Enrollment,
            student=request.user,
            course=lesson.module.course,
            status='active'
        )
        
        Note.objects.create(
            enrollment=enrollment,
            lesson=lesson,
            content=request.POST.get('content'),
            timestamp=request.POST.get('timestamp', 0)
        )
        
        messages.success(request, 'Note created successfully!')
    
    return redirect('courses:lesson_view', lesson_id=lesson_id)


@login_required
def delete_note(request, note_id):
    """Delete a note"""
    note = get_object_or_404(Note, id=note_id, enrollment__student=request.user)
    lesson_id = note.lesson.id
    note.delete()
    messages.success(request, 'Note deleted successfully!')
    return redirect('courses:lesson_view', lesson_id=lesson_id)


# Reviews
@login_required
def create_review(request, course_id):
    """Create or update a review for a course"""
    course = get_object_or_404(Course, id=course_id)
    
    # Check enrollment
    enrollment = get_object_or_404(
        Enrollment,
        student=request.user,
        course=course,
        status='active'
    )
    
    if request.method == 'POST':
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment')
        
        # Update or create review
        review, created = Review.objects.update_or_create(
            student=request.user,
            course=course,
            defaults={
                'rating': rating,
                'comment': comment
            }
        )
        
        if created:
            messages.success(request, 'Review submitted successfully!')
        else:
            messages.success(request, 'Review updated successfully!')
    
    return redirect('courses:course_detail', slug=course.slug)


# My Courses
@login_required
def my_courses(request):
    """List user's enrolled courses"""
    enrollments = Enrollment.objects.filter(
        student=request.user,
        status='active'
    ).select_related('course').order_by('-enrolled_at')
    
    context = {
        'enrollments': enrollments
    }
    
    return render(request, 'courses/my_courses.html', context)


# Teacher Course Management (RESTRICTED - can only view assigned courses)
@login_required
def teacher_courses(request):
    """List teacher's ASSIGNED courses (not created by teacher)"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Get only courses assigned to this teacher
    assignments = CourseAssignment.objects.filter(
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).select_related('course', 'course__category', 'assigned_by')
    
    course_ids = [assignment.course.id for assignment in assignments]
    
    # Base queryset - only assigned courses
    courses = Course.objects.filter(id__in=course_ids).annotate(
        student_count=Count('enrollments', filter=Q(enrollments__status='active')),
        avg_rating=Avg('reviews__rating')
    )
    
    # Apply filters
    if status_filter != 'all':
        courses = courses.filter(status=status_filter)
    
    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Apply sorting
    courses = courses.order_by(sort_by)
    
    # Calculate actual teacher revenue for each course using commission calculator
    from decimal import Decimal
    courses_list = list(courses)
    for course in courses_list:
        course_payments = Payment.objects.filter(
            course=course,
            status='completed'
        ).select_related('course')
        
        total_revenue = Decimal('0')
        for payment in course_payments:
            coupon_usage = CouponUsage.objects.filter(payment=payment).first()
            coupon = coupon_usage.coupon if coupon_usage else None
            commission_data = CommissionCalculator.calculate_commission(payment, coupon)
            total_revenue += commission_data['teacher_revenue']
        
        course.total_revenue = total_revenue
    
    # Get counts for each status
    status_counts = {
        'all': Course.objects.filter(id__in=course_ids).count(),
        'published': Course.objects.filter(id__in=course_ids, status='published').count(),
        'draft': Course.objects.filter(id__in=course_ids, status='draft').count(),
        'archived': Course.objects.filter(id__in=course_ids, status='archived').count(),
    }
    
    # Create a mapping of course to assignment for permissions
    course_assignments = {assignment.course.id: assignment for assignment in assignments}
    
    context = {
        'courses': courses_list,
        'status_filter': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'status_counts': status_counts,
        'course_assignments': course_assignments,
        'is_assigned_mode': True,  # Flag to indicate teacher can't create courses
    }
    
    return render(request, 'courses/teacher_courses.html', context)


@login_required
def teacher_course_create(request):
    """DISABLED: Teachers can no longer create courses - only platform admins"""
    messages.error(request, 'Course creation is now handled by platform administrators. Please contact admin to get courses assigned to you.')
    return redirect('courses:teacher_courses')


@login_required
def teacher_course_edit(request, course_id):
    """Edit course details - RESTRICTED based on assignment permissions"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    # Check if course is assigned to this teacher
    assignment = CourseAssignment.objects.filter(
        course_id=course_id,
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).first()
    
    if not assignment:
        messages.error(request, 'You do not have access to this course. This course must be assigned to you by a platform administrator.')
        return redirect('courses:teacher_courses')
    
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        # Check permissions for editing course details
        if assignment.can_edit_details:
            course.title = request.POST.get('title')
            course.description = request.POST.get('description')
            course.short_description = request.POST.get('short_description', '')
            course.category_id = request.POST.get('category') if request.POST.get('category') else None
            course.level = request.POST.get('level')
            course.language = request.POST.get('language')
            
            if 'thumbnail' in request.FILES:
                course.thumbnail = request.FILES['thumbnail']
        else:
            messages.warning(request, 'You do not have permission to edit course details.')
        
        # Check permission for publishing
        if assignment.can_publish and request.POST.get('status'):
            course.status = request.POST.get('status', 'draft')
        
        course.save()
        messages.success(request, 'Course updated successfully!')
        return redirect('courses:teacher_course_edit', course_id=course.id)
    
    # Get categories
    categories = Category.objects.filter(is_active=True)
    
    # Get course modules and lessons
    modules = Module.objects.filter(course=course).prefetch_related('lessons').order_by('order')
    
    # Get course stats
    student_count = Enrollment.objects.filter(course=course, status='active').count()
    
    # Calculate actual teacher revenue using commission calculator
    from decimal import Decimal
    course_payments = Payment.objects.filter(
        course=course,
        status='completed'
    ).select_related('course')
    
    total_revenue = Decimal('0')
    for payment in course_payments:
        coupon_usage = CouponUsage.objects.filter(payment=payment).first()
        coupon = coupon_usage.coupon if coupon_usage else None
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        total_revenue += commission_data['teacher_revenue']
    
    context = {
        'course': course,
        'categories': categories,
        'modules': modules,
        'student_count': student_count,
        'total_revenue': total_revenue,
        'assignment': assignment,  # Pass assignment for permission checks in template
        'can_edit_details': assignment.can_edit_details,
        'can_edit_content': assignment.can_edit_content,
        'can_publish': assignment.can_publish,
    }
    
    return render(request, 'courses/teacher_course_edit.html', context)


@login_required
def teacher_course_delete(request, course_id):
    """DISABLED: Teachers can no longer delete courses"""
    messages.error(request, 'Course deletion is now handled by platform administrators.')
    return redirect('courses:teacher_courses')


@login_required
def teacher_course_students(request, course_id):
    """View students enrolled in a course"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    # Check if course is assigned to this teacher
    assignment = CourseAssignment.objects.filter(
        course_id=course_id,
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).first()
    
    if not assignment:
        messages.error(request, 'You do not have access to this course')
        return redirect('courses:teacher_courses')
    
    course = get_object_or_404(Course, id=course_id)
    
    enrollments = Enrollment.objects.filter(course=course).select_related(
        'student', 'student__student_profile'
    ).order_by('-enrolled_at')
    
    context = {
        'course': course,
        'enrollments': enrollments,
    }
    
    return render(request, 'courses/teacher_course_students.html', context)


@login_required
def teacher_analytics(request):
    """Detailed teacher analytics page"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.payments.models import Payment
    from django.db.models import Sum, Count
    from datetime import datetime, timedelta
    from decimal import Decimal
    
    # Get or create analytics
    try:
        analytics = TeacherAnalytics.objects.get(teacher=request.user)
    except TeacherAnalytics.DoesNotExist:
        analytics = None
    
    # Revenue analytics - Calculate actual teacher earnings using commission calculator
    all_teacher_payments = Payment.objects.filter(
        course__teacher=request.user,
        status='completed'
    ).select_related('course')
    
    total_revenue = Decimal('0')
    for payment in all_teacher_payments:
        coupon_usage = CouponUsage.objects.filter(payment=payment).first()
        coupon = coupon_usage.coupon if coupon_usage else None
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        total_revenue += commission_data['teacher_revenue']
    
    # Monthly revenue for last 6 months
    monthly_revenue = []
    for i in range(5, -1, -1):
        month_start = (datetime.now() - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_payments = Payment.objects.filter(
            course__teacher=request.user,
            status='completed',
            created_at__gte=month_start,
            created_at__lte=month_end
        ).select_related('course')
        
        month_rev = Decimal('0')
        for payment in month_payments:
            coupon_usage = CouponUsage.objects.filter(payment=payment).first()
            coupon = coupon_usage.coupon if coupon_usage else None
            commission_data = CommissionCalculator.calculate_commission(payment, coupon)
            month_rev += commission_data['teacher_revenue']
        
        monthly_revenue.append({
            'month': month_start.strftime('%b %Y'),
            'revenue': month_rev
        })
    
    # Course performance
    courses = Course.objects.filter(teacher=request.user).annotate(
        student_count=Count('enrollments', filter=Q(enrollments__status='active')),
        avg_rating=Avg('reviews__rating')
    ).order_by('-student_count')
    
    # Calculate revenue for each course
    courses_list = list(courses)
    for course in courses_list:
        course_payments = Payment.objects.filter(
            course=course,
            status='completed'
        ).select_related('course')
        
        course_rev = Decimal('0')
        for payment in course_payments:
            coupon_usage = CouponUsage.objects.filter(payment=payment).first()
            coupon = coupon_usage.coupon if coupon_usage else None
            commission_data = CommissionCalculator.calculate_commission(payment, coupon)
            course_rev += commission_data['teacher_revenue']
        
        course.total_revenue = course_rev
    
    context = {
        'analytics': analytics,
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'courses': courses_list,
    }
    
    return render(request, 'courses/teacher_analytics.html', context)


@login_required
def teacher_coupon_statistics(request):
    """View teacher's assigned coupons and their statistics"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.payments.models import Coupon, CouponUsage
    from apps.platformadmin.models import CourseAssignment
    from django.db.models import Sum, Count
    from decimal import Decimal
    
    # Get all assignments for this teacher (include assigned + accepted)
    assignments = CourseAssignment.objects.filter(
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).prefetch_related('assigned_coupons')

    # Collect all coupons assigned via CourseAssignment and coupons directly assigned to teacher
    coupon_map = {}

    # Coupons from assignments
    for assignment in assignments:
        for coupon in assignment.assigned_coupons.all():
            coupon_map[coupon.id] = {
                'coupon': coupon,
                'course': assignment.course
            }

    # Also include coupons that were created/assigned directly to this teacher (Coupon.assigned_to_teacher)
    teacher_direct_coupons = Coupon.objects.filter(assigned_to_teacher=request.user)
    for coupon in teacher_direct_coupons:
        # If coupon already present via assignment, keep the course from assignment; otherwise course is None
        if coupon.id not in coupon_map:
            coupon_map[coupon.id] = {
                'coupon': coupon,
                'course': None
            }

    # Build stats list
    assigned_coupons = []
    for entry in coupon_map.values():
        coupon = entry['coupon']
        course = entry['course']
        uses = CouponUsage.objects.filter(coupon=coupon).count()
        total_revenue = CouponUsage.objects.filter(coupon=coupon).aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0')
        extra_commission = CouponUsage.objects.filter(coupon=coupon, commission_recipient=request.user).aggregate(Sum('extra_commission_earned'))['extra_commission_earned__sum'] or Decimal('0')
        coupon_stats = {
            'coupon': coupon,
            'course': course,
            'uses': uses,
            'total_revenue': total_revenue,
            'extra_commission': extra_commission,
        }
        assigned_coupons.append(coupon_stats)
    
    # Overall statistics
    total_uses = sum(c['uses'] for c in assigned_coupons)
    total_revenue = sum(c['total_revenue'] for c in assigned_coupons)
    total_extra_commission = sum(c['extra_commission'] for c in assigned_coupons)
    
    context = {
        'assigned_coupons': assigned_coupons,
        'total_uses': total_uses,
        'total_revenue': total_revenue,
        'total_extra_commission': total_extra_commission,
    }
    
    return render(request, 'courses/teacher_coupon_stats.html', context)


# ==================== MODULE MANAGEMENT ====================

@login_required
def teacher_module_create(request, course_id):
    """Create a new module for a course"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    # Check if course is assigned and teacher has content edit permission
    assignment = CourseAssignment.objects.filter(
        course_id=course_id,
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).first()
    
    if not assignment or not assignment.can_edit_content:
        messages.error(request, 'You do not have permission to add modules to this course')
        return redirect('courses:teacher_courses')
    
    course = get_object_or_404(Course, id=course_id)
    
    if request.method == 'POST':
        # Get the highest order number
        max_order = Module.objects.filter(course=course).aggregate(Max('order'))['order__max'] or 0
        
        # Create module
        module = Module.objects.create(
            course=course,
            title=request.POST.get('title'),
            description=request.POST.get('description', ''),
            order=max_order + 1,
            is_published=request.POST.get('is_published') == 'on'
        )
        
        messages.success(request, f'Module "{module.title}" created successfully!')
        return redirect('courses:teacher_course_edit', course_id=course.id)
    
    return redirect('courses:teacher_course_edit', course_id=course.id)


@login_required
def teacher_module_edit(request, module_id):
    """Edit an existing module"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    module = get_object_or_404(Module, id=module_id)
    
    # Check if course is assigned and teacher has content edit permission
    assignment = CourseAssignment.objects.filter(
        course=module.course,
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).first()
    
    if not assignment or not assignment.can_edit_content:
        messages.error(request, 'You do not have permission to edit modules in this course')
        return redirect('courses:teacher_courses')
    
    if request.method == 'POST':
        module.title = request.POST.get('title')
        module.description = request.POST.get('description', '')
        module.is_published = request.POST.get('is_published') == 'on'
        module.save()
        
        messages.success(request, f'Module "{module.title}" updated successfully!')
        return redirect('courses:teacher_course_edit', course_id=module.course.id)
    
    return redirect('courses:teacher_course_edit', course_id=module.course.id)


@login_required
def teacher_module_delete(request, module_id):
    """Delete a module"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    module = get_object_or_404(Module, id=module_id)
    
    # Check if course is assigned and teacher has content edit permission
    assignment = CourseAssignment.objects.filter(
        course=module.course,
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).first()
    
    if not assignment or not assignment.can_edit_content:
        messages.error(request, 'You do not have permission to delete modules from this course')
        return redirect('courses:teacher_courses')
    
    course_id = module.course.id
    module_title = module.title
    
    if request.method == 'POST':
        module.delete()
        messages.success(request, f'Module "{module_title}" deleted successfully!')
        return redirect('courses:teacher_course_edit', course_id=course_id)
    
    return redirect('courses:teacher_course_edit', course_id=course_id)


@login_required
def teacher_module_reorder(request, course_id):
    """Reorder modules"""
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            module_order = data.get('module_order', [])
            
            for index, module_id in enumerate(module_order):
                Module.objects.filter(id=module_id, course=course).update(order=index)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ==================== LESSON MANAGEMENT ====================

@login_required
def teacher_lesson_create(request, module_id):
    """Create a new lesson for a module"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    module = get_object_or_404(Module, id=module_id)
    
    # Check if course is assigned and teacher has content edit permission
    assignment = CourseAssignment.objects.filter(
        course=module.course,
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).first()
    
    if not assignment or not assignment.can_edit_content:
        messages.error(request, 'You do not have permission to add lessons to this course')
        return redirect('courses:teacher_courses')
    
    if request.method == 'POST':
        # Get the highest order number
        max_order = Lesson.objects.filter(module=module).aggregate(Max('order'))['order__max'] or 0
        
        # Get common lesson data
        base_title = request.POST.get('title')
        description = request.POST.get('description', '')
        lesson_type = request.POST.get('lesson_type', 'audio')
        is_free_preview = request.POST.get('is_free_preview') == 'on'
        is_published = request.POST.get('is_published') == 'on'
        text_content = request.POST.get('text_content', '')
        
        # Handle multiple media files - create separate lesson for each file
        media_files = request.FILES.getlist('media_files')
        if media_files:
            created_lessons = []
            for index, media_file in enumerate(media_files):
                # Determine media type based on file extension
                file_extension = media_file.name.split('.')[-1].lower()
                if file_extension in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                    media_type = 'video'
                    actual_lesson_type = 'video'
                else:
                    media_type = 'audio'
                    actual_lesson_type = 'audio'
                
                # Create individual lesson for each file
                if len(media_files) > 1:
                    lesson_title = f"{base_title} - Part {index + 1}"
                else:
                    lesson_title = base_title
                
                lesson = Lesson.objects.create(
                    module=module,
                    course=module.course,
                    title=lesson_title,
                    description=description,
                    lesson_type=actual_lesson_type,
                    order=max_order + index + 1,
                    is_free_preview=is_free_preview,
                    is_published=is_published,
                    text_content=text_content
                )
                
                # Attach media file to this lesson
                LessonMedia.objects.create(
                    lesson=lesson,
                    media_file=media_file,
                    media_type=media_type,
                    file_size=media_file.size,
                    order=0
                )
                
                created_lessons.append(lesson)
            
            # Use the first lesson for success message
            lesson = created_lessons[0]
            if len(media_files) > 1:
                messages.success(request, f'{len(media_files)} lessons created successfully from uploaded media files!')
            else:
                messages.success(request, f'Lesson "{lesson.title}" created successfully!')
        else:
            # Create single lesson without media files (for text lessons or legacy single file)
            lesson = Lesson.objects.create(
                module=module,
                course=module.course,
                title=base_title,
                description=description,
                lesson_type=lesson_type,
                order=max_order + 1,
                is_free_preview=is_free_preview,
                is_published=is_published,
                text_content=text_content
            )
            
            # Handle file upload if provided (legacy single file)
            if 'audio_file' in request.FILES:
                audio_file = request.FILES['audio_file']
                lesson.audio_file = audio_file
                lesson.file_size = audio_file.size
                lesson.save()
            
            messages.success(request, f'Lesson "{lesson.title}" created successfully!')
        
        return redirect('courses:teacher_course_edit', course_id=module.course.id)
    
    return redirect('courses:teacher_course_edit', course_id=module.course.id)


@login_required
def teacher_lesson_edit(request, lesson_id):
    """Edit an existing lesson"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    # Check if course is assigned and teacher has content edit permission
    assignment = CourseAssignment.objects.filter(
        course=lesson.course,
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).first()
    
    if not assignment or not assignment.can_edit_content:
        messages.error(request, 'You do not have permission to edit lessons in this course')
        return redirect('courses:teacher_courses')
    
    if request.method == 'POST':
        lesson.title = request.POST.get('title')
        lesson.description = request.POST.get('description', '')
        lesson.lesson_type = request.POST.get('lesson_type', 'audio')
        lesson.is_free_preview = request.POST.get('is_free_preview') == 'on'
        lesson.is_published = request.POST.get('is_published') == 'on'
        lesson.text_content = request.POST.get('text_content', '')
        
        # Handle file upload if provided (legacy single file)
        if 'audio_file' in request.FILES:
            audio_file = request.FILES['audio_file']
            lesson.audio_file = audio_file
            lesson.file_size = audio_file.size
        
        lesson.save()
        
        # Handle multiple media files
        media_files = request.FILES.getlist('media_files')
        if media_files:
            # Get the current max order
            max_order = LessonMedia.objects.filter(lesson=lesson).aggregate(Max('order'))['order__max'] or -1
            
            for index, media_file in enumerate(media_files):
                # Determine media type based on file extension
                file_extension = media_file.name.split('.')[-1].lower()
                if file_extension in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                    media_type = 'video'
                else:
                    media_type = 'audio'
                
                LessonMedia.objects.create(
                    lesson=lesson,
                    media_file=media_file,
                    media_type=media_type,
                    file_size=media_file.size,
                    order=max_order + index + 1
                )
        
        messages.success(request, f'Lesson "{lesson.title}" updated successfully!')
        return redirect('courses:teacher_course_edit', course_id=lesson.course.id)
    
    return redirect('courses:teacher_course_edit', course_id=lesson.course.id)


@login_required
def teacher_lesson_delete(request, lesson_id):
    """Delete a lesson"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    lesson = get_object_or_404(Lesson, id=lesson_id, course__teacher=request.user)
    course_id = lesson.course.id
    lesson_title = lesson.title
    
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, f'Lesson "{lesson_title}" deleted successfully!')
        return redirect('courses:teacher_course_edit', course_id=course_id)
    
    return redirect('courses:teacher_course_edit', course_id=course_id)


@login_required
def teacher_lesson_reorder(request, module_id):
    """Reorder lessons within a module"""
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    module = get_object_or_404(Module, id=module_id, course__teacher=request.user)
    
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            lesson_order = data.get('lesson_order', [])
            
            for index, lesson_id in enumerate(lesson_order):
                Lesson.objects.filter(id=lesson_id, module=module).update(order=index)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def teacher_lesson_media_delete(request, media_id):
    """Delete a lesson media file"""
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    media = get_object_or_404(LessonMedia, id=media_id, lesson__course__teacher=request.user)
    
    if request.method == 'POST':
        lesson_id = media.lesson.course.id
        media.delete()
        messages.success(request, 'Media file deleted successfully!')
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ==================== AUDIO FILE SERVING ====================

@login_required
@require_http_methods(["GET", "HEAD"])
def serve_lesson_audio(request, slug):
    """
    Serve audio files with proper headers for browser playback.
    Supports range requests for seeking.
    """
    lesson = get_object_or_404(Lesson, slug=slug)
    
    # Check if user has access to this lesson
    # Either enrolled or it's a free preview
    if not lesson.is_free_preview:
        enrollment = Enrollment.objects.filter(
            student=request.user,
            course=lesson.course,
            status='active'
        ).first()
        
        if not enrollment and not request.user.is_teacher:
            return HttpResponse('Unauthorized', status=401)
    
    # Check if audio file exists
    if not lesson.audio_file:
        return HttpResponse('No audio file available', status=404)
    
    try:
        # Get the file path
        file_path = lesson.audio_file.path
        
        if not os.path.exists(file_path):
            return HttpResponse('Audio file not found', status=404)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'audio/mpeg'  # Default to MP3
        
        # Handle range requests for seeking
        range_header = request.META.get('HTTP_RANGE', '').strip()
        range_match = None
        
        if range_header:
            import re
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        
        if range_match:
            # Partial content response (for seeking)
            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
            
            if start >= file_size:
                return HttpResponse('Requested Range Not Satisfiable', status=416)
            
            end = min(end, file_size - 1)
            length = end - start + 1
            
            with open(file_path, 'rb') as audio_file:
                audio_file.seek(start)
                data = audio_file.read(length)
            
            response = HttpResponse(data, status=206, content_type=content_type)
            response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response['Content-Length'] = str(length)
        else:
            # Full file response
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            response['Content-Length'] = str(file_size)
        
        # Set headers for audio playback
        response['Accept-Ranges'] = 'bytes'
        response['Cache-Control'] = 'public, max-age=3600'
        
        # CORS headers if needed
        if hasattr(request, 'META') and 'HTTP_ORIGIN' in request.META:
            response['Access-Control-Allow-Origin'] = '*'
        
        return response
        
    except Exception as e:
        return HttpResponse(f'Error serving audio: {str(e)}', status=500)


# ==================== TEACHER STUDENTS MANAGEMENT ====================

@login_required
def teacher_students_list(request):
    """List all students enrolled in teacher's courses"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    # Get all enrollments for teacher's courses
    enrollments = Enrollment.objects.filter(
        course__teacher=request.user
    ).select_related(
        'student', 'course', 'student__student_profile'
    ).prefetch_related(
        'lesson_progress'
    ).order_by('-enrolled_at')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        enrollments = enrollments.filter(status=status_filter)
    
    # Filter by course
    course_filter = request.GET.get('course')
    if course_filter:
        enrollments = enrollments.filter(course_id=course_filter)
    
    # Search
    search = request.GET.get('search', '').strip()
    if search:
        enrollments = enrollments.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__email__icontains=search) |
            Q(course__title__icontains=search)
        )
    
    # Stats
    stats = {
        'total': Enrollment.objects.filter(course__teacher=request.user).count(),
        'active': Enrollment.objects.filter(course__teacher=request.user, status='active').count(),
        'completed': Enrollment.objects.filter(course__teacher=request.user, status='completed').count(),
        'unique_students': Enrollment.objects.filter(
            course__teacher=request.user
        ).values('student').distinct().count()
    }
    
    # Get teacher's courses for filter
    teacher_courses = Course.objects.filter(teacher=request.user).only('id', 'title')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(enrollments, 25)
    page = request.GET.get('page', 1)
    enrollments_page = paginator.get_page(page)
    
    context = {
        'enrollments': enrollments_page,
        'stats': stats,
        'teacher_courses': teacher_courses,
        'status_filter': status_filter,
        'course_filter': course_filter,
        'search': search,
    }
    
    return render(request, 'courses/teacher_students.html', context)


@login_required
def teacher_student_detail(request, enrollment_id):
    """Detailed view of a student's progress"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    enrollment = get_object_or_404(
        Enrollment.objects.select_related(
            'student', 'course', 'student__student_profile'
        ).prefetch_related(
            'lesson_progress__lesson', 'notes'
        ),
        id=enrollment_id,
        course__teacher=request.user
    )
    
    # Get all lesson progress
    lesson_progress = enrollment.lesson_progress.all().order_by('lesson__order')
    
    # Get notes
    notes = enrollment.notes.select_related('lesson').order_by('-created_at')
    
    # Calculate detailed stats
    total_lessons = enrollment.course.lessons.count()
    completed_lessons = lesson_progress.filter(is_completed=True).count()
    
    context = {
        'enrollment': enrollment,
        'lesson_progress': lesson_progress,
        'notes': notes,
        'total_lessons': total_lessons,
        'completed_lessons': completed_lessons,
    }
    
    return render(request, 'courses/teacher_student_detail.html', context)


# ==================== TEACHER REVIEWS MANAGEMENT ====================

@login_required
def teacher_reviews_list(request):
    """List all reviews for teacher's courses"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    reviews = Review.objects.filter(
        course__teacher=request.user
    ).select_related(
        'student', 'course', 'enrollment'
    ).order_by('-created_at')
    
    # Filter by rating
    rating_filter = request.GET.get('rating')
    if rating_filter:
        reviews = reviews.filter(rating=rating_filter)
    
    # Filter by course
    course_filter = request.GET.get('course')
    if course_filter:
        reviews = reviews.filter(course_id=course_filter)
    
    # Filter by approval status
    approval_filter = request.GET.get('approved')
    if approval_filter == 'pending':
        reviews = reviews.filter(is_approved=False)
    elif approval_filter == 'approved':
        reviews = reviews.filter(is_approved=True)
    
    # Search
    search = request.GET.get('search', '').strip()
    if search:
        reviews = reviews.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(comment__icontains=search) |
            Q(title__icontains=search)
        )
    
    # Stats
    stats = {
        'total': Review.objects.filter(course__teacher=request.user).count(),
        'avg_rating': Review.objects.filter(
            course__teacher=request.user, is_approved=True
        ).aggregate(avg=Avg('rating'))['avg'] or 0,
        'pending': Review.objects.filter(course__teacher=request.user, is_approved=False).count(),
    }
    
    # Rating distribution
    rating_distribution = {}
    for i in range(1, 6):
        rating_distribution[i] = Review.objects.filter(
            course__teacher=request.user, rating=i
        ).count()
    
    # Get teacher's courses for filter
    teacher_courses = Course.objects.filter(teacher=request.user).only('id', 'title')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(reviews, 20)
    page = request.GET.get('page', 1)
    reviews_page = paginator.get_page(page)
    
    context = {
        'reviews': reviews_page,
        'stats': stats,
        'rating_distribution': rating_distribution,
        'teacher_courses': teacher_courses,
        'rating_filter': rating_filter,
        'course_filter': course_filter,
        'approval_filter': approval_filter,
        'search': search,
    }
    
    return render(request, 'courses/teacher_reviews.html', context)


@login_required
@require_http_methods(["POST"])
def teacher_review_toggle_approval(request, review_id):
    """Toggle review approval status"""
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    review = get_object_or_404(Review, id=review_id, course__teacher=request.user)
    review.is_approved = not review.is_approved
    review.save()
    
    return JsonResponse({
        'success': True,
        'is_approved': review.is_approved
    })


# ==================== TEACHER BULK OPERATIONS ====================

@login_required
@require_http_methods(["POST"])
def teacher_bulk_course_action(request):
    """Bulk actions for courses"""
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    action = request.POST.get('action')
    course_ids = request.POST.getlist('course_ids[]')
    
    if not course_ids:
        return JsonResponse({'success': False, 'error': 'No courses selected'})
    
    courses = Course.objects.filter(id__in=course_ids, teacher=request.user)
    
    if action == 'publish':
        courses.update(status='published')
        message = f'{courses.count()} courses published successfully'
    elif action == 'draft':
        courses.update(status='draft')
        message = f'{courses.count()} courses moved to draft'
    elif action == 'archive':
        courses.update(status='archived')
        message = f'{courses.count()} courses archived'
    elif action == 'delete':
        count = courses.count()
        courses.delete()
        message = f'{count} courses deleted successfully'
    else:
        return JsonResponse({'success': False, 'error': 'Invalid action'})
    
    return JsonResponse({'success': True, 'message': message})


# ==================== TEACHER EXPORT FEATURES ====================

@login_required
def teacher_export_students(request):
    """Export students data to CSV"""
    if not request.user.is_teacher:
        return HttpResponse('Unauthorized', status=403)
    
    import csv
    from django.http import HttpResponse
    from datetime import datetime
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="students_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student Name', 'Email', 'Course', 'Enrolled Date', 'Status', 'Progress %', 'Lessons Completed'])
    
    enrollments = Enrollment.objects.filter(
        course__teacher=request.user
    ).select_related('student', 'course').order_by('-enrolled_at')
    
    for enrollment in enrollments:
        writer.writerow([
            enrollment.student.get_full_name() or enrollment.student.email,
            enrollment.student.email,
            enrollment.course.title,
            enrollment.enrolled_at.strftime('%Y-%m-%d %H:%M'),
            enrollment.status,
            f'{enrollment.progress_percentage}%',
            enrollment.lessons_completed
        ])
    
    return response


@login_required
def teacher_export_earnings(request):
    """Export earnings data to CSV"""
    if not request.user.is_teacher:
        return HttpResponse('Unauthorized', status=403)
    
    import csv
    from django.http import HttpResponse
    from datetime import datetime
    from apps.payments.models import Payment
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="earnings_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Student', 'Course', 'Amount', 'Status', 'Payment Reference'])
    
    payments = Payment.objects.filter(
        course__teacher=request.user,
        status='completed'
    ).select_related('user', 'course').order_by('-created_at')
    
    for payment in payments:
        writer.writerow([
            payment.created_at.strftime('%Y-%m-%d %H:%M'),
            payment.user.get_full_name() or payment.user.email,
            payment.course.title,
            payment.amount,
            payment.status,
            payment.payment_id or payment.order_id
        ])
    
    return response


# ==================== COURSE PREVIEW & DUPLICATION ====================

@login_required
def teacher_course_preview(request, course_id):
    """Preview course before publishing"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    # Check if course is assigned to this teacher
    assignment = CourseAssignment.objects.filter(
        course_id=course_id,
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).first()
    
    if not assignment:
        messages.error(request, 'You do not have access to this course')
        return redirect('courses:teacher_courses')
    
    course = get_object_or_404(
        Course.objects.prefetch_related('modules__lessons'),
        id=course_id
    )
    
    # Calculate course stats
    total_lessons = sum(module.lessons.count() for module in course.modules.all())
    total_duration = sum(
        lesson.duration_seconds or 0 
        for module in course.modules.all() 
        for lesson in module.lessons.all()
    )
    
    context = {
        'course': course,
        'total_lessons': total_lessons,
        'total_duration': total_duration,
        'is_preview': True,
    }
    
    return render(request, 'courses/teacher_course_preview.html', context)


@login_required
@require_http_methods(["POST"])
def teacher_course_duplicate(request, course_id):
    """DISABLED: Teachers can no longer duplicate courses - only platform admins"""
    return JsonResponse({'success': False, 'error': 'Course duplication is now handled by platform administrators'})
    
    # Create duplicate course
    duplicate = Course.objects.get(pk=original_course.pk)
    duplicate.pk = None
    duplicate.id = None
    duplicate.title = f"{original_course.title} (Copy)"
    duplicate.slug = f"{original_course.slug}-copy-{uuid.uuid4().hex[:8]}"
    duplicate.status = 'draft'
    duplicate.save()
    
    # Duplicate modules and lessons
    for module in original_course.modules.all():
        old_module_pk = module.pk
        module.pk = None
        module.id = None
        module.course = duplicate
        module.save()
        
        # Get lessons from original module
        from apps.courses.models import Lesson
        original_lessons = Lesson.objects.filter(module_id=old_module_pk)
        
        for lesson in original_lessons:
            lesson.pk = None
            lesson.id = None
            lesson.module = module
            lesson.save()
    
    messages.success(request, f'Course duplicated successfully! Edit your new course: {duplicate.title}')
    return JsonResponse({
        'success': True,
        'redirect_url': f'/courses/teacher/courses/{duplicate.id}/edit/'
    })


# ==================== COURSE ASSIGNMENT ACCEPTANCE/REJECTION ====================

@login_required
@require_http_methods(["POST"])
def teacher_accept_assignment(request, assignment_id):
    """Teacher accepts a course assignment"""
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    from apps.platformadmin.models import CourseAssignment
    
    assignment = get_object_or_404(CourseAssignment, id=assignment_id, teacher=request.user)
    
    if assignment.status != 'assigned':
        return JsonResponse({'success': False, 'error': 'This assignment cannot be accepted'})
    
    assignment.status = 'accepted'
    assignment.accepted_at = timezone.now()
    assignment.save()
    
    messages.success(request, f'You have accepted the assignment for "{assignment.course.title}"')
    return JsonResponse({
        'success': True,
        'message': f'Assignment accepted for {assignment.course.title}',
        'redirect_url': '/users/teacher-dashboard/'
    })


@login_required
@require_http_methods(["POST"])
def teacher_reject_assignment(request, assignment_id):
    """Teacher rejects a course assignment"""
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    from apps.platformadmin.models import CourseAssignment
    
    assignment = get_object_or_404(CourseAssignment, id=assignment_id, teacher=request.user)
    
    if assignment.status != 'assigned':
        return JsonResponse({'success': False, 'error': 'This assignment cannot be rejected'})
    
    rejection_reason = request.POST.get('reason', '')
    
    assignment.status = 'rejected'
    assignment.rejected_at = timezone.now()
    assignment.rejection_reason = rejection_reason
    assignment.save()
    
    messages.info(request, f'You have rejected the assignment for "{assignment.course.title}"')
    return JsonResponse({
        'success': True,
        'message': f'Assignment rejected for {assignment.course.title}',
        'redirect_url': '/users/teacher-dashboard/'
    })


@login_required
def teacher_view_assignments(request):
    """View all course assignments (pending, accepted, rejected)"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from apps.platformadmin.models import CourseAssignment
    
    # Get all assignments
    all_assignments = CourseAssignment.objects.filter(
        teacher=request.user
    ).select_related('course', 'assigned_by', 'course__category').order_by('-assigned_at')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        all_assignments = all_assignments.filter(status=status_filter)
    
    # Status counts
    status_counts = {
        'all': CourseAssignment.objects.filter(teacher=request.user).count(),
        'assigned': CourseAssignment.objects.filter(teacher=request.user, status='assigned').count(),
        'accepted': CourseAssignment.objects.filter(teacher=request.user, status='accepted').count(),
        'rejected': CourseAssignment.objects.filter(teacher=request.user, status='rejected').count(),
        'revoked': CourseAssignment.objects.filter(teacher=request.user, status='revoked').count(),
    }
    
    context = {
        'assignments': all_assignments,
        'status_filter': status_filter,
        'status_counts': status_counts,
    }
    
    return render(request, 'courses/teacher_assignments.html', context)



