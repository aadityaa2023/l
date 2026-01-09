"""
Student-specific views for profile, goals, and preferences
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta
from .models import User, StudentProfile
from apps.courses.models import Course, Enrollment, Review
from apps.payments.models import Payment, Subscription
from apps.analytics.models import StudentAnalytics, ListeningSession


# ==================== LEARNING GOALS ====================

@login_required
def student_learning_goals(request):
    """Manage learning goals"""
    student_profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'set_weekly_goal':
            hours = request.POST.get('weekly_hours')
            try:
                hours = int(hours)
                if 1 <= hours <= 50:
                    student_profile.weekly_goal_hours = hours
                    student_profile.save()
                    messages.success(request, f'Weekly goal set to {hours} hours')
                else:
                    messages.error(request, 'Weekly goal must be between 1 and 50 hours')
            except ValueError:
                messages.error(request, 'Invalid number')
        
        elif action == 'set_daily_goal':
            minutes = request.POST.get('daily_minutes')
            try:
                minutes = int(minutes)
                if 5 <= minutes <= 480:
                    student_profile.daily_goal_minutes = minutes
                    student_profile.save()
                    messages.success(request, f'Daily goal set to {minutes} minutes')
                else:
                    messages.error(request, 'Daily goal must be between 5 and 480 minutes')
            except ValueError:
                messages.error(request, 'Invalid number')
        
        return redirect('users:student_learning_goals')
    
    # Calculate current progress
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    
    # Daily progress
    daily_sessions = ListeningSession.objects.filter(
        user=request.user,
        started_at__date=today
    ).aggregate(total=Sum('duration_seconds'))
    
    daily_minutes = (daily_sessions['total'] or 0) / 60
    daily_progress = min(100, (daily_minutes / (student_profile.daily_goal_minutes or 30)) * 100)
    
    # Weekly progress
    weekly_sessions = ListeningSession.objects.filter(
        user=request.user,
        started_at__date__gte=week_start
    ).aggregate(total=Sum('duration_seconds'))
    
    weekly_hours = (weekly_sessions['total'] or 0) / 3600
    weekly_progress = min(100, (weekly_hours / (student_profile.weekly_goal_hours or 5)) * 100)
    
    # Get analytics
    try:
        analytics = StudentAnalytics.objects.get(student=request.user)
    except StudentAnalytics.DoesNotExist:
        analytics = None
    
    context = {
        'student_profile': student_profile,
        'daily_minutes': daily_minutes,
        'daily_progress': daily_progress,
        'weekly_hours': weekly_hours,
        'weekly_progress': weekly_progress,
        'analytics': analytics,
    }
    
    return render(request, 'users/student_learning_goals.html', context)


# ==================== BILLING & PAYMENTS ====================

@login_required
def student_billing_history(request):
    """View payment and subscription history"""
    # Get all payments
    payments = Payment.objects.filter(
        user=request.user
    ).select_related('course').order_by('-created_at')
    
    # Get all subscriptions
    subscriptions = Subscription.objects.filter(
        user=request.user
    ).select_related('course').order_by('-created_at')
    
    # Filter by status
    payment_status = request.GET.get('status', 'all')
    if payment_status != 'all':
        payments = payments.filter(status=payment_status)
    
    subscription_status = request.GET.get('sub_status', 'all')
    if subscription_status != 'all':
        subscriptions = subscriptions.filter(status=subscription_status)
    
    # Calculate totals
    total_spent = payments.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    active_subscriptions_count = subscriptions.filter(status='active').count()
    
    stats = {
        'total_spent': total_spent,
        'total_payments': payments.count(),
        'active_subscriptions': active_subscriptions_count,
        'completed_payments': payments.filter(status='completed').count(),
    }
    
    # Pagination
    from django.core.paginator import Paginator
    paginator_payments = Paginator(payments, 15)
    paginator_subs = Paginator(subscriptions, 10)
    
    page = request.GET.get('page', 1)
    payments_page = paginator_payments.get_page(page)
    
    sub_page = request.GET.get('sub_page', 1)
    subscriptions_page = paginator_subs.get_page(sub_page)
    
    context = {
        'payments': payments_page,
        'subscriptions': subscriptions_page,
        'stats': stats,
        'payment_status': payment_status,
        'subscription_status': subscription_status,
    }
    
    return render(request, 'users/student_billing.html', context)


# ==================== COURSE RECOMMENDATIONS ====================

def get_student_recommendations(user, limit=6):
    """Get personalized course recommendations for student"""
    # Get enrolled courses
    enrolled_course_ids = Enrollment.objects.filter(
        student=user
    ).values_list('course_id', flat=True)
    
    # Get categories from enrolled courses
    enrolled_categories = Course.objects.filter(
        id__in=enrolled_course_ids
    ).values_list('category_id', flat=True).distinct()
    
    # Recommend courses from same categories
    recommendations = Course.objects.filter(
        status='published',
        category_id__in=enrolled_categories
    ).exclude(
        id__in=enrolled_course_ids
    ).annotate(
        student_count=Count('enrollments'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-avg_rating', '-student_count')[:limit]
    
    # If no recommendations, get popular courses
    if recommendations.count() < limit:
        popular = Course.objects.filter(
            status='published'
        ).exclude(
            id__in=enrolled_course_ids
        ).annotate(
            student_count=Count('enrollments'),
            avg_rating=Avg('reviews__rating')
        ).order_by('-student_count', '-avg_rating')[:limit]
        
        return list(recommendations) + list(popular[:limit - recommendations.count()])
    
    return recommendations


# ==================== ACHIEVEMENTS ====================

@login_required
def student_achievements(request):
    """View student achievements and badges"""
    try:
        analytics = StudentAnalytics.objects.get(student=request.user)
    except StudentAnalytics.DoesNotExist:
        analytics = None
    
    # Calculate achievements
    achievements = []
    
    # Course completion achievements
    completed_courses = Enrollment.objects.filter(
        student=request.user,
        status='completed'
    ).count()
    
    if completed_courses >= 1:
        achievements.append({
            'title': 'First Course',
            'description': 'Completed your first course',
            'icon': 'fa-trophy',
            'color': 'warning',
            'unlocked': True,
            'date': Enrollment.objects.filter(
                student=request.user,
                status='completed'
            ).order_by('completed_at').first().completed_at if completed_courses > 0 else None
        })
    
    if completed_courses >= 5:
        achievements.append({
            'title': '5 Course Master',
            'description': 'Completed 5 courses',
            'icon': 'fa-star',
            'color': 'primary',
            'unlocked': True
        })
    
    if completed_courses >= 10:
        achievements.append({
            'title': 'Learning Expert',
            'description': 'Completed 10 courses',
            'icon': 'fa-crown',
            'color': 'success',
            'unlocked': True
        })
    
    # Streak achievements
    current_streak = analytics.current_streak if analytics else 0
    
    if current_streak >= 7:
        achievements.append({
            'title': '7 Day Streak',
            'description': 'Learn for 7 consecutive days',
            'icon': 'fa-fire',
            'color': 'danger',
            'unlocked': True
        })
    
    if current_streak >= 30:
        achievements.append({
            'title': '30 Day Streak',
            'description': 'Learn for 30 consecutive days',
            'icon': 'fa-fire-alt',
            'color': 'danger',
            'unlocked': True
        })
    
    # Listening time achievements
    total_hours = analytics.total_listening_hours if analytics else 0
    
    if total_hours >= 10:
        achievements.append({
            'title': '10 Hour Learner',
            'description': 'Listened to 10 hours of content',
            'icon': 'fa-headphones',
            'color': 'info',
            'unlocked': True
        })
    
    if total_hours >= 50:
        achievements.append({
            'title': '50 Hour Master',
            'description': 'Listened to 50 hours of content',
            'icon': 'fa-headphones-alt',
            'color': 'info',
            'unlocked': True
        })
    
    # Review achievements
    review_count = Review.objects.filter(student=request.user).count()
    
    if review_count >= 5:
        achievements.append({
            'title': 'Helpful Reviewer',
            'description': 'Left 5 course reviews',
            'icon': 'fa-comment-dots',
            'color': 'secondary',
            'unlocked': True
        })
    
    context = {
        'achievements': achievements,
        'analytics': analytics,
        'total_achievements': len(achievements),
    }
    
    return render(request, 'users/student_achievements.html', context)
