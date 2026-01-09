from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from django.utils import timezone
from .models import Notification, Message, CourseQuestion, QuestionAnswer
from apps.courses.models import Course


# ==================== NOTIFICATIONS ====================

@login_required
def notifications_list(request):
    """List all user notifications"""
    notifications = Notification.objects.filter(
        user=request.user
    ).select_related('course', 'lesson').order_by('-created_at')
    
    # Mark as read filter
    unread_only = request.GET.get('unread') == 'true'
    if unread_only:
        notifications = notifications.filter(is_read=False)
    
    # Count unread
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page', 1)
    notifications_page = paginator.get_page(page)
    
    context = {
        'notifications': notifications_page,
        'unread_count': unread_count,
        'unread_only': unread_only,
    }
    
    return render(request, 'notifications/list.html', context)


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    return JsonResponse({'success': True})


@login_required
def get_unread_notifications_count(request):
    """API endpoint to get unread notifications count"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})


# ==================== MESSAGES ====================

@login_required
def messages_inbox(request):
    """Teacher's message inbox"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    received_messages = Message.objects.filter(
        recipient=request.user,
        parent__isnull=True  # Only show parent messages
    ).select_related('sender', 'course').prefetch_related('replies').order_by('-created_at')
    
    # Filter
    unread_only = request.GET.get('unread') == 'true'
    if unread_only:
        received_messages = received_messages.filter(is_read=False)
    
    # Stats
    stats = {
        'total': Message.objects.filter(recipient=request.user).count(),
        'unread': Message.objects.filter(recipient=request.user, is_read=False).count(),
    }
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(received_messages, 20)
    page = request.GET.get('page', 1)
    messages_page = paginator.get_page(page)
    
    context = {
        'messages': messages_page,
        'stats': stats,
        'unread_only': unread_only,
    }
    
    return render(request, 'notifications/messages_inbox.html', context)


@login_required
def message_detail(request, message_id):
    """View a message thread"""
    message = get_object_or_404(
        Message.objects.select_related('sender', 'recipient', 'course').prefetch_related('replies__sender'),
        id=message_id
    )
    
    # Check permission
    if message.sender != request.user and message.recipient != request.user:
        messages.error(request, 'You do not have permission to view this message')
        return redirect('notifications:messages_inbox')
    
    # Mark as read if recipient
    if message.recipient == request.user and not message.is_read:
        message.is_read = True
        message.read_at = timezone.now()
        message.save()
    
    # Handle reply
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            # Get the root message
            root_message = message if message.parent is None else message.parent
            
            reply = Message.objects.create(
                sender=request.user,
                recipient=message.sender if message.sender != request.user else message.recipient,
                subject=f"Re: {root_message.subject}",
                body=body,
                course=message.course,
                parent=root_message
            )
            
            # Create notification
            Notification.objects.create(
                user=reply.recipient,
                notification_type='message',
                title='New Message Reply',
                message=f'{request.user.get_full_name() or request.user.email} replied to your message',
                link_url=f'/notifications/messages/{root_message.id}/',
            )
            
            messages.success(request, 'Reply sent successfully!')
            return redirect('notifications:message_detail', message_id=root_message.id)
    
    # Get root message for thread
    root_message = message if message.parent is None else message.parent
    
    context = {
        'message': root_message,
        'replies': root_message.replies.all().order_by('created_at'),
    }
    
    return render(request, 'notifications/message_detail.html', context)


@login_required
def message_compose(request, student_id=None):
    """Compose a new message"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Get recipient if specified
    recipient = None
    if student_id:
        recipient = get_object_or_404(User, id=student_id)
    
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient_id')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        course_id = request.POST.get('course_id')
        
        if not recipient_id or not subject or not body:
            messages.error(request, 'Please fill all required fields')
        else:
            recipient = get_object_or_404(User, id=recipient_id)
            
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                body=body,
                course_id=course_id if course_id else None
            )
            
            # Create notification
            Notification.objects.create(
                user=recipient,
                notification_type='message',
                title='New Message',
                message=f'{request.user.get_full_name() or request.user.email} sent you a message',
                link_url=f'/notifications/messages/{message.id}/',
            )
            
            messages.success(request, 'Message sent successfully!')
            return redirect('notifications:messages_inbox')
    
    # Get teacher's students for recipient list
    from apps.courses.models import Enrollment
    students = User.objects.filter(
        enrollments__course__teacher=request.user
    ).distinct().order_by('first_name', 'email')
    
    # Get teacher's courses
    courses = Course.objects.filter(teacher=request.user).only('id', 'title')
    
    context = {
        'recipient': recipient,
        'students': students,
        'courses': courses,
    }
    
    return render(request, 'notifications/message_compose.html', context)


@login_required
def student_messages_inbox(request):
    """Student's message inbox"""
    received_messages = Message.objects.filter(
        recipient=request.user,
        parent__isnull=True
    ).select_related('sender', 'course').prefetch_related('replies').order_by('-created_at')
    
    sent_messages = Message.objects.filter(
        sender=request.user,
        parent__isnull=True
    ).select_related('recipient', 'course').prefetch_related('replies').order_by('-created_at')
    
    # Filter
    view_type = request.GET.get('view', 'received')
    unread_only = request.GET.get('unread') == 'true'
    
    if view_type == 'sent':
        messages_list = sent_messages
    else:
        messages_list = received_messages
        if unread_only:
            messages_list = messages_list.filter(is_read=False)
    
    # Stats
    stats = {
        'received': received_messages.count(),
        'sent': sent_messages.count(),
        'unread': received_messages.filter(is_read=False).count(),
    }
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(messages_list, 15)
    page = request.GET.get('page', 1)
    messages_page = paginator.get_page(page)
    
    context = {
        'messages': messages_page,
        'stats': stats,
        'view_type': view_type,
        'unread_only': unread_only,
    }
    
    return render(request, 'notifications/student_messages.html', context)


@login_required
def student_message_compose(request, teacher_id=None):
    """Compose message to teacher"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Get recipient (teacher) if specified
    recipient = None
    if teacher_id:
        recipient = get_object_or_404(User, id=teacher_id, role='teacher')
    
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient_id')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        course_id = request.POST.get('course_id')
        
        if not recipient_id or not subject or not body:
            messages.error(request, 'Please fill all required fields')
        else:
            recipient = get_object_or_404(User, id=recipient_id, role='teacher')
            
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                body=body,
                course_id=course_id if course_id else None
            )
            
            # Create notification
            Notification.objects.create(
                user=recipient,
                notification_type='message',
                title='New Message',
                message=f'{request.user.get_full_name() or request.user.email} sent you a message',
                link_url=f'/notifications/messages/{message.id}/',
            )
            
            messages.success(request, 'Message sent successfully!')
            return redirect('notifications:student_messages')
    
    # Get student's enrolled courses teachers
    from apps.courses.models import Enrollment
    teachers = User.objects.filter(
        courses__enrollments__student=request.user,
        role='teacher'
    ).distinct().order_by('first_name', 'email')
    
    # Get student's courses
    courses = Course.objects.filter(
        enrollments__student=request.user
    ).distinct().only('id', 'title')
    
    context = {
        'recipient': recipient,
        'teachers': teachers,
        'courses': courses,
        # Template expects `enrolled_courses` when rendering the course select dropdown
        'enrolled_courses': courses,
    }
    
    return render(request, 'notifications/student_message_compose.html', context)


# ==================== Q&A SYSTEM ====================

@login_required
def teacher_questions_list(request):
    """List all questions from students"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    questions = CourseQuestion.objects.filter(
        course__teacher=request.user
    ).select_related('student', 'course', 'lesson').annotate(
        answer_count=Count('answers')
    ).order_by('-created_at')
    
    # Filter
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'unanswered':
        questions = questions.filter(is_answered=False)
    elif status_filter == 'answered':
        questions = questions.filter(is_answered=True)
    
    course_filter = request.GET.get('course')
    if course_filter:
        questions = questions.filter(course_id=course_filter)
    
    # Stats
    stats = {
        'total': CourseQuestion.objects.filter(course__teacher=request.user).count(),
        'unanswered': CourseQuestion.objects.filter(course__teacher=request.user, is_answered=False).count(),
        'answered': CourseQuestion.objects.filter(course__teacher=request.user, is_answered=True).count(),
    }
    
    # Get teacher's courses for filter
    teacher_courses = Course.objects.filter(teacher=request.user).only('id', 'title')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(questions, 20)
    page = request.GET.get('page', 1)
    questions_page = paginator.get_page(page)
    
    context = {
        'questions': questions_page,
        'stats': stats,
        'teacher_courses': teacher_courses,
        'status_filter': status_filter,
        'course_filter': course_filter,
    }
    
    return render(request, 'notifications/teacher_questions.html', context)


@login_required
def question_detail(request, question_id):
    """View and answer a question"""
    question = get_object_or_404(
        CourseQuestion.objects.select_related('student', 'course', 'lesson').prefetch_related('answers__user'),
        id=question_id
    )
    
    # Check permission
    if question.course.teacher != request.user and question.student != request.user:
        messages.error(request, 'You do not have permission to view this question')
        return redirect('users:dashboard')
    
    # Handle answer submission
    if request.method == 'POST' and request.user.is_teacher:
        answer_text = request.POST.get('answer', '').strip()
        if answer_text:
            answer = QuestionAnswer.objects.create(
                question=question,
                user=request.user,
                answer=answer_text
            )
            
            # Create notification for student
            Notification.objects.create(
                user=question.student,
                notification_type='question',
                title='Question Answered',
                message=f'Your question "{question.title}" has been answered',
                link_url=f'/notifications/questions/{question.id}/',
                course=question.course
            )
            
            messages.success(request, 'Answer posted successfully!')
            return redirect('notifications:question_detail', question_id=question.id)
    
    context = {
        'question': question,
        'answers': question.answers.all(),
    }
    
    return render(request, 'notifications/question_detail.html', context)


@login_required
@require_http_methods(["POST"])
def mark_best_answer(request, answer_id):
    """Mark an answer as the best answer"""
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    answer = get_object_or_404(QuestionAnswer, id=answer_id, question__course__teacher=request.user)
    answer.is_best_answer = True
    answer.save()
    
    return JsonResponse({'success': True})


# ==================== STUDENT SPECIFIC VIEWS ====================

@login_required
def student_questions_list(request):
    """List student's questions"""
    questions = CourseQuestion.objects.filter(
        student=request.user
    ).select_related('course', 'lesson').annotate(
        answer_count=Count('answers')
    ).order_by('-created_at')
    
    # Filter
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'unanswered':
        questions = questions.filter(is_answered=False)
    elif status_filter == 'answered':
        questions = questions.filter(is_answered=True)
    
    course_filter = request.GET.get('course')
    if course_filter:
        questions = questions.filter(course_id=course_filter)
    
    # Stats
    stats = {
        'total': CourseQuestion.objects.filter(student=request.user).count(),
        'unanswered': CourseQuestion.objects.filter(student=request.user, is_answered=False).count(),
        'answered': CourseQuestion.objects.filter(student=request.user, is_answered=True).count(),
    }
    
    # Get student's courses for filter
    from apps.courses.models import Enrollment
    student_courses = Course.objects.filter(
        enrollments__student=request.user
    ).distinct().only('id', 'title')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(questions, 15)
    page = request.GET.get('page', 1)
    questions_page = paginator.get_page(page)
    
    context = {
        'questions': questions_page,
        'stats': stats,
        'student_courses': student_courses,
        'status_filter': status_filter,
        'course_filter': course_filter,
    }
    
    return render(request, 'notifications/student_questions.html', context)


@login_required
def student_ask_question(request, lesson_id=None):
    """Ask a question about a lesson"""
    from apps.courses.models import Lesson, Enrollment
    
    lesson = None
    if lesson_id:
        lesson = get_object_or_404(Lesson, id=lesson_id)
        # Verify student is enrolled
        if not Enrollment.objects.filter(student=request.user, course=lesson.course).exists():
            messages.error(request, 'You must be enrolled to ask questions')
            return redirect('courses:course_detail', slug=lesson.course.slug)
    
    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        lesson_id = request.POST.get('lesson_id')
        title = request.POST.get('title', '').strip()
        question_text = request.POST.get('question', '').strip()
        
        if not course_id or not title or not question_text:
            messages.error(request, 'Please fill all required fields')
        else:
            course = get_object_or_404(Course, id=course_id)
            
            # Verify enrollment
            if not Enrollment.objects.filter(student=request.user, course=course).exists():
                messages.error(request, 'You must be enrolled to ask questions')
                return redirect('courses:course_detail', slug=course.slug)
            
            question = CourseQuestion.objects.create(
                student=request.user,
                course=course,
                lesson_id=lesson_id if lesson_id else None,
                title=title,
                question=question_text
            )
            
            # Notify teacher
            Notification.objects.create(
                user=course.teacher,
                notification_type='question',
                title='New Question',
                message=f'{request.user.get_full_name() or request.user.email} asked: {title}',
                link_url=f'/notifications/questions/{question.id}/',
                course=course
            )
            
            messages.success(request, 'Question submitted successfully!')
            return redirect('notifications:student_questions')
    
    # Get student's enrolled courses
    enrolled_courses = Course.objects.filter(
        enrollments__student=request.user
    ).distinct()
    
    context = {
        'lesson': lesson,
        'enrolled_courses': enrolled_courses,
    }
    
    return render(request, 'notifications/student_ask_question.html', context)


@login_required
def student_messages_inbox(request):
    """Student's message inbox"""
    received_messages = Message.objects.filter(
        recipient=request.user,
        parent__isnull=True
    ).select_related('sender', 'course').prefetch_related('replies').order_by('-created_at')
    
    sent_messages = Message.objects.filter(
        sender=request.user,
        parent__isnull=True
    ).select_related('recipient', 'course').prefetch_related('replies').order_by('-created_at')
    
    # Filter
    view_type = request.GET.get('view', 'received')
    unread_only = request.GET.get('unread') == 'true'
    
    if view_type == 'sent':
        messages_list = sent_messages
    else:
        messages_list = received_messages
        if unread_only:
            messages_list = messages_list.filter(is_read=False)
    
    # Stats
    stats = {
        'received': received_messages.count(),
        'sent': sent_messages.count(),
        'unread': received_messages.filter(is_read=False).count(),
    }
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(messages_list, 15)
    page = request.GET.get('page', 1)
    messages_page = paginator.get_page(page)
    
    context = {
        'messages': messages_page,
        'stats': stats,
        'view_type': view_type,
        'unread_only': unread_only,
    }
    
    return render(request, 'notifications/student_messages.html', context)


@login_required
def student_message_compose_to_teacher(request, teacher_id=None):
    """Compose message to teacher"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Get recipient (teacher) if specified
    recipient = None
    if teacher_id:
        recipient = get_object_or_404(User, id=teacher_id, role='teacher')
    
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient_id')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        course_id = request.POST.get('course_id')
        
        if not recipient_id or not subject or not body:
            messages.error(request, 'Please fill all required fields')
        else:
            recipient = get_object_or_404(User, id=recipient_id, role='teacher')
            
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                body=body,
                course_id=course_id if course_id else None
            )
            
            # Create notification
            Notification.objects.create(
                user=recipient,
                notification_type='message',
                title='New Message',
                message=f'{request.user.get_full_name() or request.user.email} sent you a message',
                link_url=f'/notifications/messages/{message.id}/',
            )
            
            messages.success(request, 'Message sent successfully!')
            return redirect('notifications:student_messages')
    
    # Get student's enrolled courses teachers
    from apps.courses.models import Enrollment
    teachers = User.objects.filter(
        courses__enrollments__student=request.user,
        role='teacher'
    ).distinct().order_by('first_name', 'email')
    
    # Get student's courses
    courses = Course.objects.filter(
        enrollments__student=request.user
    ).distinct().only('id', 'title')
    
    context = {
        'recipient': recipient,
        'teachers': teachers,
        'courses': courses,
    }
    
    return render(request, 'notifications/student_message_compose.html', context)


