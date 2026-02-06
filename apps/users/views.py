"""
User views for authentication and profile management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Count, Avg, Q, Sum
from .models import User, StudentProfile, TeacherProfile, Address
from apps.courses.models import Enrollment, Course, Review
from apps.analytics.models import StudentAnalytics, TeacherAnalytics
from apps.payments.models import Payment, Subscription, CouponUsage
from apps.payments.commission_calculator import CommissionCalculator


# Dashboard Views
@login_required
def dashboard_redirect(request):
    """Redirect to appropriate dashboard based on user role"""
    if request.user.is_teacher:
        return redirect('users:teacher_dashboard')
    else:
        return redirect('users:student_dashboard')


@login_required
def student_dashboard(request):
    """Student dashboard view - Redirect to My Learning"""
    return redirect('courses:my_courses')


@login_required
def teacher_dashboard(request):
    """Enhanced teacher dashboard view with comprehensive analytics"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:student_dashboard')
    
    teacher_profile, created = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={'bio': '', 'expertise': ''}
    )
    
    from apps.payments.models import Payment
    from apps.platformadmin.models import CourseAssignment
    from django.db.models import Sum
    from datetime import datetime, timedelta
    
    # Get teacher's ASSIGNED courses with detailed stats (hiding student stats as requested)
    assignments = CourseAssignment.objects.filter(
        teacher=request.user,
        status__in=['assigned', 'accepted']
    ).select_related('course')
    
    course_ids = [assignment.course.id for assignment in assignments]
    courses = Course.objects.filter(id__in=course_ids).annotate(
        # student_count=Count('enrollments', filter=Q(enrollments__status='active')),  # Hidden as requested
        avg_rating=Avg('reviews__rating'),
        total_revenue=Sum('enrollments__payment_amount', filter=Q(enrollments__status='active'))
    ).order_by('-created_at')
    
    # Get pending assignments
    pending_assignments = CourseAssignment.objects.filter(
        teacher=request.user,
        status='assigned'
    ).select_related('course', 'assigned_by')
    
    # Course status counts
    courses_published = Course.objects.filter(id__in=course_ids, status='published').count()
    courses_draft = Course.objects.filter(id__in=course_ids, status='draft').count()
    courses_archived = Course.objects.filter(id__in=course_ids, status='archived').count()
    
    # Get teacher analytics
    try:
        analytics = TeacherAnalytics.objects.get(teacher=request.user)
    except TeacherAnalytics.DoesNotExist:
        analytics = None
    
    # Hide student statistics as requested by removing these sections
    # total_students = Enrollment.objects.filter(
    #     course__id__in=course_ids,
    #     status='active'
    # ).values('student').distinct().count()
    # 
    # # Recent enrollments with course details
    # recent_enrollments = Enrollment.objects.filter(
    #     course__id__in=course_ids
    # ).select_related('student', 'course').order_by('-enrolled_at')[:10]
    
    total_students = 0  # Hide student count
    recent_enrollments = []  # Hide recent enrollments
    
    # Get recent reviews (keeping this as it's about course feedback, not student stats)
    recent_reviews = Review.objects.filter(
        course__id__in=course_ids
    ).select_related('student', 'course').order_by('-created_at')[:5]
    
    # Revenue calculations - Calculate actual teacher earnings using commission calculator
    from decimal import Decimal
    from datetime import timedelta
    from django.utils import timezone
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    seven_days_ago = timezone.now() - timedelta(days=7)
    yesterday_start = (timezone.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = (timezone.now() - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Calculate revenue for last 30 days
    payments_30days = Payment.objects.filter(
        course__id__in=course_ids,
        status='completed',
        created_at__gte=thirty_days_ago
    ).select_related('course')
    
    revenue_30days = Decimal('0')
    for payment in payments_30days:
        coupon_usage = CouponUsage.objects.filter(payment=payment).first()
        coupon = coupon_usage.coupon if coupon_usage else None
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        revenue_30days += commission_data['teacher_revenue']
    
    # Calculate revenue for last 7 days
    payments_7days = Payment.objects.filter(
        course__id__in=course_ids,
        status='completed',
        created_at__gte=seven_days_ago
    ).select_related('course')
    
    revenue_7days = Decimal('0')
    for payment in payments_7days:
        coupon_usage = CouponUsage.objects.filter(payment=payment).first()
        coupon = coupon_usage.coupon if coupon_usage else None
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        revenue_7days += commission_data['teacher_revenue']
    
    # Calculate revenue for yesterday
    payments_yesterday = Payment.objects.filter(
        course__id__in=course_ids,
        status='completed',
        created_at__gte=yesterday_start,
        created_at__lte=yesterday_end
    ).select_related('course')
    
    revenue_yesterday = Decimal('0')
    for payment in payments_yesterday:
        coupon_usage = CouponUsage.objects.filter(payment=payment).first()
        coupon = coupon_usage.coupon if coupon_usage else None
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        revenue_yesterday += commission_data['teacher_revenue']
    
    # Calculate total revenue
    total_payments = Payment.objects.filter(
        course__id__in=course_ids,
        status='completed'
    ).select_related('course')
    
    total_revenue = Decimal('0')
    for payment in total_payments:
        coupon_usage = CouponUsage.objects.filter(payment=payment).first()
        coupon = coupon_usage.coupon if coupon_usage else None
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        total_revenue += commission_data['teacher_revenue']
    
    # Enrollment trends (last 7 days)
    enrollment_trend = []
    for i in range(6, -1, -1):
        day = timezone.now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        count = Enrollment.objects.filter(
            course__id__in=course_ids,
            enrolled_at__gte=day_start,
            enrolled_at__lte=day_end
        ).count()
        enrollment_trend.append({
            'date': day.strftime('%b %d'),
            'count': count
        })
    
    # Top performing courses
    top_courses = courses.filter(status='published').order_by('-total_enrollments', '-average_rating')[:5]
    
    context = {
        'teacher_profile': teacher_profile,
        'courses': courses[:6],  # Show only recent 6 on dashboard
        'total_courses': courses.count(),
        'courses_published': courses_published,
        'courses_draft': courses_draft,
        'courses_archived': courses_archived,
        'analytics': analytics,
        'total_students': total_students,
        'recent_enrollments': recent_enrollments,
        'recent_reviews': recent_reviews,
        'revenue_30days': revenue_30days,
        'revenue_7days': revenue_7days,
        'revenue_yesterday': revenue_yesterday,
        'total_revenue': total_revenue,
        'enrollment_trend': enrollment_trend,
        'top_courses': top_courses,
        'pending_assignments': pending_assignments,  # New assignments awaiting acceptance
    }
    
    return render(request, 'users/teacher_dashboard.html', context)


# Profile Views
class ProfileDetailView(LoginRequiredMixin, DetailView):
    """User profile detail view"""
    model = User
    template_name = 'users/profile_detail.html'
    context_object_name = 'profile_user'
    
    def get_object(self):
        return self.request.user


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Update user profile"""
    model = User
    # Only include fields that exist on the User model here.
    # `bio` and `profile_picture` live on the related StudentProfile/TeacherProfile
    # and are saved explicitly in `form_valid` below.
    fields = ['first_name', 'last_name', 'phone']
    template_name = 'users/profile_update.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        # Save user fields first
        user = form.save()

        # Ensure related profile exists and save profile-specific fields
        # Profile fields may come from POST or FILES (for profile_picture)
        bio = self.request.POST.get('bio', None)
        profile_pic = self.request.FILES.get('profile_picture') if self.request.method == 'POST' else None

        if getattr(self.request.user, 'is_teacher', False):
            teacher_profile, created = TeacherProfile.objects.get_or_create(
                user=self.request.user,
                defaults={'bio': '', 'expertise': ''}
            )
            if bio is not None:
                teacher_profile.bio = bio
            if profile_pic:
                teacher_profile.profile_picture = profile_pic
            teacher_profile.save()
        else:
            student_profile, created = StudentProfile.objects.get_or_create(
                user=self.request.user
            )
            if bio is not None:
                student_profile.bio = bio
            if profile_pic:
                student_profile.profile_picture = profile_pic
            student_profile.save()

        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)


@login_required
def update_student_profile(request):
    """Update student-specific profile information"""
    student_profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update student profile fields
        student_profile.grade = request.POST.get('grade')
        student_profile.school = request.POST.get('school')
        student_profile.learning_goals = request.POST.get('learning_goals')
        student_profile.save()
        
        messages.success(request, 'Student profile updated successfully!')
        return redirect('users:profile')
    
    context = {
        'student_profile': student_profile
    }
    return render(request, 'users/student_profile_update.html', context)


@login_required
def update_teacher_profile(request):
    """Update teacher-specific profile information"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:profile')
    
    teacher_profile, created = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={'bio': '', 'expertise': ''}
    )
    
    if request.method == 'POST':
        # Update teacher profile fields
        teacher_profile.expertise = request.POST.get('expertise')
        teacher_profile.qualifications = request.POST.get('qualifications')
        teacher_profile.teaching_experience = request.POST.get('teaching_experience')
        teacher_profile.linkedin_url = request.POST.get('linkedin_url')
        teacher_profile.website = request.POST.get('website')
        teacher_profile.save()
        
        messages.success(request, 'Teacher profile updated successfully!')
        return redirect('users:profile')
    
    context = {
        'teacher_profile': teacher_profile
    }
    return render(request, 'users/teacher_profile_update.html', context)


# Address Management
@login_required
def manage_addresses(request):
    """Manage user addresses"""
    addresses = Address.objects.filter(user=request.user)
    
    if request.method == 'POST':
        # Create new address
        Address.objects.create(
            user=request.user,
            address_type=request.POST.get('address_type'),
            street_address=request.POST.get('street_address'),
            city=request.POST.get('city'),
            state=request.POST.get('state'),
            postal_code=request.POST.get('postal_code'),
            country=request.POST.get('country', 'India'),
            is_default=request.POST.get('is_default') == 'on'
        )
        
        messages.success(request, 'Address added successfully!')
        return redirect('users:manage_addresses')
    
    context = {
        'addresses': addresses
    }
    return render(request, 'users/manage_addresses.html', context)


@login_required
def delete_address(request, address_id):
    """Delete an address"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.delete()
    messages.success(request, 'Address deleted successfully!')
    return redirect('users:manage_addresses')


@login_required
def set_default_address(request, address_id):
    """Set an address as default"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    # Remove default from other addresses
    Address.objects.filter(user=request.user).update(is_default=False)
    
    # Set this address as default
    address.is_default = True
    address.save()
    
    messages.success(request, 'Default address updated!')
    return redirect('users:manage_addresses')


# ==================== TEACHER SETTINGS ====================

@login_required
def teacher_settings(request):
    """Teacher settings and preferences"""
    if not request.user.is_teacher:
        messages.error(request, 'You do not have teacher access')
        return redirect('users:dashboard')
    
    # Get or create teacher profile
    teacher_profile, created = TeacherProfile.objects.get_or_create(
        user=request.user,
        defaults={'bio': '', 'expertise': ''}
    )
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            # Update teacher profile
            teacher_profile.bio = request.POST.get('bio', '')
            teacher_profile.expertise = request.POST.get('expertise', '')
            teacher_profile.social_linkedin = request.POST.get('social_linkedin', '')
            teacher_profile.social_twitter = request.POST.get('social_twitter', '')
            teacher_profile.social_youtube = request.POST.get('social_youtube', '')
            teacher_profile.social_website = request.POST.get('social_website', '')
            teacher_profile.save()
            
            messages.success(request, 'Profile updated successfully!')
            
        elif action == 'update_preferences':
            # Update user preferences (you might want to add a Preferences model)
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.save()
            
            messages.success(request, 'Preferences updated successfully!')
            
        return redirect('users:teacher_settings')
    
    # Get stats
    from apps.courses.models import Course, Enrollment
    stats = {
        'total_courses': Course.objects.filter(teacher=request.user).count(),
        'published_courses': Course.objects.filter(teacher=request.user, status='published').count(),
        'total_students': Enrollment.objects.filter(course__teacher=request.user).values('student').distinct().count(),
    }
    
    context = {
        'teacher_profile': teacher_profile,
        'stats': stats,
    }
    
    return render(request, 'users/teacher_settings.html', context)


# Teacher Public Profile
def teacher_public_profile(request, teacher_id):
    """Public teacher profile view"""
    teacher = get_object_or_404(User, id=teacher_id, role='teacher')
    
    # Get teacher's courses
    courses = Course.objects.filter(
        teacher=teacher,
        status='published'
    ).annotate(
        student_count=Count('enrollments', filter=Q(enrollments__status='active')),
        avg_rating=Avg('reviews__rating')
    )
    
    # Get teacher analytics
    try:
        analytics = TeacherAnalytics.objects.get(teacher=teacher)
    except TeacherAnalytics.DoesNotExist:
        analytics = None
    
    # Get recent reviews
    reviews = Review.objects.filter(
        course__teacher=teacher
    ).select_related('student', 'course').order_by('-created_at')[:10]
    
    # Get or create teacher profile
    teacher_profile, created = TeacherProfile.objects.get_or_create(
        user=teacher,
        defaults={'bio': '', 'expertise': ''}
    )
    
    context = {
        'teacher': teacher,
        'teacher_profile': teacher_profile,
        'courses': courses,
        'analytics': analytics,
        'reviews': reviews,
    }
    
    return render(request, 'users/teacher_public_profile.html', context)


# Logout View
@login_required
def logout_view(request):
    """Logout user"""
    logout(request)
    messages.success(request, 'You have been logged out successfully!')
    return redirect('home')
