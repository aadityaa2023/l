"""
Comprehensive Platform Admin Views
All missing features for complete platform management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from datetime import timedelta
from decimal import Decimal
from django.utils.text import slugify
from django.db import IntegrityError

from apps.platformadmin.decorators import platformadmin_required
from apps.platformadmin.utils import get_context_data, ActivityLog
from apps.platformadmin.models import (
    LoginHistory, CMSPage, FAQ, Announcement, InstructorPayout,
    VideoSettings
)
from apps.courses.models import Course, Review, Enrollment
from apps.payments.models import Payment, Subscription, Coupon, CouponUsage
from apps.notifications.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()


# ============================================================================
# COUPON & PROMO CODE MANAGEMENT
# ============================================================================

@platformadmin_required
def coupon_management(request):
    """Manage discount coupons and promo codes"""
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    coupons = Coupon.objects.all()
    
    if status_filter:
        coupons = coupons.filter(status=status_filter)
    
    if search:
        coupons = coupons.filter(
            Q(code__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(coupons.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['coupons'] = page_obj.object_list
    context['status_filter'] = status_filter
    context['search'] = search
    
    # Stats
    context['coupon_stats'] = {
        'total': coupons.count(),
        'active': Coupon.objects.filter(status='active').count(),
        'total_uses': CouponUsage.objects.count(),
        'total_discount': CouponUsage.objects.aggregate(Sum('discount_amount'))['discount_amount__sum'] or 0,
    }
    
    return render(request, 'platformadmin/coupon_management.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def coupon_create(request):
    """Create new coupon"""
    if request.method == 'POST':
        # Extract form data
        code = request.POST.get('code', '').upper()
        description = request.POST.get('description', '')
        discount_type = request.POST.get('discount_type')
        discount_value = request.POST.get('discount_value')
        max_discount = request.POST.get('max_discount_amount')
        min_purchase = request.POST.get('min_purchase_amount', 0)
        valid_from = request.POST.get('valid_from')
        valid_until = request.POST.get('valid_until')
        max_uses = request.POST.get('max_uses')
        max_uses_per_user = request.POST.get('max_uses_per_user', 1)
        
        try:
            coupon = Coupon.objects.create(
                code=code,
                description=description,
                discount_type=discount_type,
                discount_value=Decimal(discount_value),
                max_discount_amount=Decimal(max_discount) if max_discount else None,
                min_purchase_amount=Decimal(min_purchase),
                valid_from=valid_from,
                valid_until=valid_until,
                max_uses=int(max_uses) if max_uses else None,
                max_uses_per_user=int(max_uses_per_user),
                created_by=request.user
            )
            
            # Log action
            ActivityLog.log_action(
                request.user, 'create', 'Coupon', str(coupon.id), code,
                {}, {'code': code, 'discount': discount_value}
            )
            
            messages.success(request, f"Coupon '{code}' created successfully.")
            return redirect('platformadmin:coupon_management')
        
        except Exception as e:
            messages.error(request, f"Error creating coupon: {str(e)}")
    
    context = get_context_data(request)
    context['courses'] = Course.objects.filter(status='published')
    return render(request, 'platformadmin/coupon_create.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def coupon_edit(request, coupon_id):
    """Edit existing coupon"""
    coupon = get_object_or_404(Coupon, id=coupon_id)
    
    if request.method == 'POST':
        old_values = {
            'status': coupon.status,
            'discount_value': str(coupon.discount_value)
        }
        
        coupon.description = request.POST.get('description', '')
        coupon.status = request.POST.get('status', 'active')
        
        # Only update if provided
        if 'discount_value' in request.POST:
            coupon.discount_value = Decimal(request.POST['discount_value'])
        
        coupon.save()
        
        # Log action
        ActivityLog.log_action(
            request.user, 'update', 'Coupon', str(coupon.id), coupon.code,
            old_values, {'status': coupon.status, 'discount_value': str(coupon.discount_value)}
        )
        
        messages.success(request, f"Coupon '{coupon.code}' updated successfully.")
        return redirect('platformadmin:coupon_management')
    
    context = get_context_data(request)
    context['coupon'] = coupon
    context['usage_stats'] = {
        'total_uses': coupon.usages.count(),
        'unique_users': coupon.usages.values('user').distinct().count(),
        'total_discount': coupon.usages.aggregate(Sum('discount_amount'))['discount_amount__sum'] or 0,
    }
    return render(request, 'platformadmin/coupon_edit.html', context)


# ============================================================================
# REVIEW & RATING MODERATION
# ============================================================================

@platformadmin_required
def review_moderation(request):
    """Moderate course reviews and ratings"""
    status_filter = request.GET.get('status', '')
    rating_filter = request.GET.get('rating', '')
    search = request.GET.get('search', '')
    
    reviews = Review.objects.select_related('student', 'course').all()
    
    if status_filter == 'approved':
        reviews = reviews.filter(is_approved=True)
    elif status_filter == 'pending':
        reviews = reviews.filter(is_approved=False)
    
    if rating_filter:
        reviews = reviews.filter(rating=int(rating_filter))
    
    if search:
        reviews = reviews.filter(
            Q(course__title__icontains=search) |
            Q(student__email__icontains=search) |
            Q(comment__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(reviews.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['reviews'] = page_obj.object_list
    context['status_filter'] = status_filter
    context['rating_filter'] = rating_filter
    context['search'] = search
    
    # Stats
    context['review_stats'] = {
        'total': Review.objects.count(),
        'approved': Review.objects.filter(is_approved=True).count(),
        'pending': Review.objects.filter(is_approved=False).count(),
        'avg_rating': Review.objects.aggregate(Avg('rating'))['rating__avg'] or 0,
    }
    
    return render(request, 'platformadmin/review_moderation.html', context)


@platformadmin_required
@require_POST
def review_approve(request, review_id):
    """Approve a review"""
    review = get_object_or_404(Review, id=review_id)
    review.is_approved = True
    review.save()
    
    # Log action
    ActivityLog.log_action(
        request.user, 'approve', 'Review', str(review.id),
        f"Review by {review.student.email}",
        {'is_approved': False}, {'is_approved': True}
    )
    
    messages.success(request, "Review approved successfully.")
    return redirect('platformadmin:review_moderation')


@platformadmin_required
@require_POST
def review_delete(request, review_id):
    """Delete/reject a review"""
    review = get_object_or_404(Review, id=review_id)
    reason = request.POST.get('reason', 'Inappropriate content')
    
    # Log action before deletion
    ActivityLog.log_action(
        request.user, 'delete', 'Review', str(review.id),
        f"Review by {review.student.email}",
        {'rating': review.rating, 'comment': review.comment[:50]}, {},
        reason=reason
    )
    
    review.delete()
    messages.success(request, "Review deleted successfully.")
    return redirect('platformadmin:review_moderation')


# ============================================================================
# SUBSCRIPTION MANAGEMENT
# ============================================================================

@platformadmin_required
def subscription_management(request):
    """Manage user subscriptions"""
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    subscriptions = Subscription.objects.select_related('user', 'course').all()
    
    if status_filter:
        subscriptions = subscriptions.filter(status=status_filter)
    
    if search:
        subscriptions = subscriptions.filter(
            Q(user__email__icontains=search) |
            Q(course__title__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(subscriptions.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['subscriptions'] = page_obj.object_list
    context['status_filter'] = status_filter
    context['search'] = search
    
    # Stats
    context['subscription_stats'] = {
        'total': subscriptions.count(),
        'active': Subscription.objects.filter(status='active').count(),
        'cancelled': Subscription.objects.filter(status='cancelled').count(),
        'expired': Subscription.objects.filter(status='expired').count(),
    }
    
    return render(request, 'platformadmin/subscription_management.html', context)


@platformadmin_required
@require_POST
def subscription_cancel(request, subscription_id):
    """Cancel a subscription"""
    subscription = get_object_or_404(Subscription, id=subscription_id)
    reason = request.POST.get('reason', 'Admin action')
    
    old_status = subscription.status
    subscription.status = 'cancelled'
    subscription.save()
    
    # Log action
    ActivityLog.log_action(
        request.user, 'update', 'Subscription', str(subscription.id),
        f"{subscription.user.email} - {subscription.course.title}",
        {'status': old_status}, {'status': 'cancelled'},
        reason=reason
    )
    
    messages.success(request, "Subscription cancelled successfully.")
    return redirect('platformadmin:subscription_management')


# ============================================================================
# INSTRUCTOR EARNINGS & PAYOUTS
# ============================================================================

@platformadmin_required
def instructor_earnings(request):
    """View instructor earnings dashboard"""
    instructor_filter = request.GET.get('instructor', '')
    
    # Get all teachers with earnings
    teachers = User.objects.filter(role='teacher').annotate(
        total_sales=Sum('courses__payments__amount', filter=Q(courses__payments__status='completed')),
        total_students=Count('courses__payments', filter=Q(courses__payments__status='completed'), distinct=True)
    ).order_by('-total_sales')
    
    if instructor_filter:
        teachers = teachers.filter(id=instructor_filter)
    
    # Pagination
    paginator = Paginator(teachers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['teachers'] = page_obj.object_list
    context['instructor_filter'] = instructor_filter
    
    # Overall stats
    total_revenue = Payment.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    platform_commission_rate = Decimal('0.30')  # 30% as Decimal fraction

    # Precompute per-teacher commission/net values to avoid template filters
    teachers_list = context['teachers']
    for teacher in teachers_list:
        sales = Decimal(teacher.total_sales or 0)
        teacher.platform_commission = (sales * platform_commission_rate)
        teacher.net_earnings = (sales * (Decimal('1.00') - platform_commission_rate))

    context['earnings_stats'] = {
        'total_revenue': total_revenue,
        'platform_earnings': Decimal(total_revenue) * platform_commission_rate,
        'instructor_earnings': Decimal(total_revenue) * (Decimal('1.00') - platform_commission_rate),
        'pending_payouts': InstructorPayout.objects.filter(status='requested').count(),
    }
    
    return render(request, 'platformadmin/instructor_earnings.html', context)


@platformadmin_required
def payout_management(request):
    """Manage instructor payout requests"""
    status_filter = request.GET.get('status', '')
    
    payouts = InstructorPayout.objects.select_related('instructor', 'processed_by').all()
    
    if status_filter:
        payouts = payouts.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(payouts.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['payouts'] = page_obj.object_list
    context['status_filter'] = status_filter
    
    # Stats
    context['payout_stats'] = {
        'total_requested': InstructorPayout.objects.filter(status='requested').count(),
        'total_amount': InstructorPayout.objects.filter(status='requested').aggregate(Sum('net_amount'))['net_amount__sum'] or 0,
        'completed_this_month': InstructorPayout.objects.filter(
            status='completed',
            processed_at__month=timezone.now().month
        ).count(),
    }
    
    return render(request, 'platformadmin/payout_management.html', context)


@platformadmin_required
@require_POST
def payout_approve(request, payout_id):
    """Approve payout request"""
    payout = get_object_or_404(InstructorPayout, id=payout_id)
    
    transaction_ref = request.POST.get('transaction_reference', '')
    admin_notes = request.POST.get('admin_notes', '')
    
    payout.status = 'completed'
    payout.processed_by = request.user
    payout.processed_at = timezone.now()
    payout.transaction_reference = transaction_ref
    payout.admin_notes = admin_notes
    payout.save()
    
    # Log action
    ActivityLog.log_action(
        request.user, 'approve', 'InstructorPayout', str(payout.id),
        f"{payout.instructor.email} - ₹{payout.net_amount}",
        {'status': 'requested'}, {'status': 'completed'}
    )
    
    messages.success(request, f"Payout of ₹{payout.net_amount} approved for {payout.instructor.email}")
    return redirect('platformadmin:payout_management')


@platformadmin_required
@require_POST
def payout_reject(request, payout_id):
    """Reject payout request"""
    payout = get_object_or_404(InstructorPayout, id=payout_id)
    
    rejection_reason = request.POST.get('rejection_reason', '')
    
    payout.status = 'rejected'
    payout.processed_by = request.user
    payout.processed_at = timezone.now()
    payout.rejection_reason = rejection_reason
    payout.save()
    
    # Log action
    ActivityLog.log_action(
        request.user, 'reject', 'InstructorPayout', str(payout.id),
        f"{payout.instructor.email} - ₹{payout.net_amount}",
        {'status': 'requested'}, {'status': 'rejected'},
        reason=rejection_reason
    )
    
    messages.success(request, "Payout request rejected.")
    return redirect('platformadmin:payout_management')


# ============================================================================
# LOGIN HISTORY & SECURITY
# ============================================================================

@platformadmin_required
def login_history(request):
    """View login history and security logs"""
    user_filter = request.GET.get('user', '')
    status_filter = request.GET.get('status', '')
    
    logs = LoginHistory.objects.select_related('user').all()
    
    if user_filter:
        logs = logs.filter(Q(user__email__icontains=user_filter) | Q(email__icontains=user_filter))
    
    if status_filter:
        logs = logs.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(logs.order_by('-attempted_at'), 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['logs'] = page_obj.object_list
    context['user_filter'] = user_filter
    context['status_filter'] = status_filter
    
    # Stats
    last_24h = timezone.now() - timedelta(hours=24)
    context['security_stats'] = {
        'total_logins_24h': LoginHistory.objects.filter(attempted_at__gte=last_24h, status='success').count(),
        'failed_attempts_24h': LoginHistory.objects.filter(attempted_at__gte=last_24h, status='failed').count(),
        'unique_ips_24h': LoginHistory.objects.filter(attempted_at__gte=last_24h).values('ip_address').distinct().count(),
        'blocked_attempts': LoginHistory.objects.filter(status='blocked').count(),
    }
    
    return render(request, 'platformadmin/login_history.html', context)


@platformadmin_required
def student_progress(request):
    """Track student progress and completion"""
    search = request.GET.get('search', '')
    course_filter = request.GET.get('course', '')
    
    enrollments = Enrollment.objects.select_related('student', 'course').all()
    
    if search:
        enrollments = enrollments.filter(
            Q(student__email__icontains=search) |
            Q(course__title__icontains=search)
        )
    
    if course_filter:
        enrollments = enrollments.filter(course_id=course_filter)
    
    # Pagination
    paginator = Paginator(enrollments.order_by('-enrolled_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['enrollments'] = page_obj.object_list
    context['search'] = search
    context['course_filter'] = course_filter
    context['courses'] = Course.objects.filter(status='published')
    
    # Stats
    context['progress_stats'] = {
        'total_enrollments': enrollments.count(),
        'completed': enrollments.filter(is_completed=True).count(),
        'in_progress': enrollments.filter(is_completed=False, progress_percentage__gt=0).count(),
        'not_started': enrollments.filter(progress_percentage=0).count(),
    }
    
    return render(request, 'platformadmin/student_progress.html', context)


# ============================================================================
# CMS MANAGEMENT
# ============================================================================

@platformadmin_required
def cms_management(request):
    """Manage CMS pages"""
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    pages = CMSPage.objects.all()
    
    if status_filter == 'published':
        pages = pages.filter(status='published')
    elif status_filter == 'draft':
        pages = pages.filter(status='draft')
    
    if search:
        pages = pages.filter(Q(title__icontains=search) | Q(slug__icontains=search))
    
    # Pagination
    paginator = Paginator(pages.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['pages'] = page_obj.object_list
    context['status_filter'] = status_filter
    context['search'] = search
    context['stats'] = {
        'total_pages': CMSPage.objects.count(),
        'published_pages': CMSPage.objects.filter(status='published').count(),
        'draft_pages': CMSPage.objects.filter(status='draft').count(),
    }
    
    return render(request, 'platformadmin/cms_management.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def cms_page_create(request):
    """Create new CMS page"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip()
        content = request.POST.get('content', '').strip()
        status = request.POST.get('status', 'draft')

        # Basic validation
        if not title:
            messages.error(request, "Title is required to create a page.")
            context = get_context_data(request)
            context['title'] = title
            context['slug'] = slug
            context['content'] = content
            context['status'] = status
            return render(request, 'platformadmin/cms_page_create.html', context)

        # Auto-generate slug from title if not provided
        if not slug:
            slug = slugify(title)[:50]

        # Ensure slug uniqueness
        base_slug = slug
        counter = 1
        while CMSPage.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        try:
            page = CMSPage.objects.create(
                title=title,
                slug=slug,
                content=content,
                status=status,
                created_by=request.user
            )
            messages.success(request, f"Page '{title}' created successfully.")
            return redirect('platformadmin:cms_management')
        except IntegrityError as e:
            messages.error(request, f"Error creating page: {str(e)}")
            context = get_context_data(request)
            context['title'] = title
            context['slug'] = slug
            context['content'] = content
            context['status'] = status
            return render(request, 'platformadmin/cms_page_create.html', context)
    
    context = get_context_data(request)
    return render(request, 'platformadmin/cms_page_create.html', context)


@platformadmin_required
def faq_management(request):
    """Manage FAQs"""
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    faqs = FAQ.objects.all()
    
    if category_filter:
        faqs = faqs.filter(category=category_filter)
    
    if status_filter == 'active':
        faqs = faqs.filter(is_active=True)
    elif status_filter == 'inactive':
        faqs = faqs.filter(is_active=False)
    
    if search:
        faqs = faqs.filter(Q(question__icontains=search) | Q(answer__icontains=search))
    
    # Pagination
    paginator = Paginator(faqs.order_by('category', 'order'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['faqs'] = page_obj.object_list
    context['category_filter'] = category_filter
    context['status_filter'] = status_filter
    context['search'] = search
    context['categories'] = FAQ.objects.values_list('category', flat=True).distinct()
    context['stats'] = {
        'total_faqs': FAQ.objects.count(),
        'active_faqs': FAQ.objects.filter(is_active=True).count(),
        'categories_count': FAQ.objects.values('category').distinct().count(),
    }
    
    return render(request, 'platformadmin/faq_management.html', context)


@platformadmin_required
def announcement_management(request):
    """Manage platform announcements"""
    target_filter = request.GET.get('target', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    announcements = Announcement.objects.all()
    
    if target_filter:
        announcements = announcements.filter(target_audience=target_filter)
    
    if status_filter == 'active':
        announcements = announcements.filter(is_active=True)
    elif status_filter == 'scheduled':
        announcements = announcements.filter(start_date__gt=timezone.now())
    elif status_filter == 'expired':
        announcements = announcements.filter(end_date__lt=timezone.now())
    
    if search:
        announcements = announcements.filter(Q(title__icontains=search) | Q(message__icontains=search))
    
    # Pagination
    paginator = Paginator(announcements.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['announcements'] = page_obj.object_list
    context['target_filter'] = target_filter
    context['status_filter'] = status_filter
    context['search'] = search
    context['today'] = timezone.now().date()
    context['stats'] = {
        'total_announcements': Announcement.objects.count(),
        'active_announcements': Announcement.objects.filter(is_active=True).count(),
        'scheduled_announcements': Announcement.objects.filter(start_date__gt=timezone.now()).count(),
        'draft_announcements': Announcement.objects.filter(is_active=False).count(),
    }
    
    return render(request, 'platformadmin/announcement_management.html', context)


# ============================================================================
# MARKETING & REFERRAL
# ============================================================================

@platformadmin_required
# MARKETING & REFERRAL
# Referral features removed: UI, routes and admin registrations disabled.
# Referral-related models remain in the codebase for data retention, but
# admin pages and platformadmin views/templates have been removed.


# ============================================================================
# VIDEO/CONTENT CONTROL
# ============================================================================

@platformadmin_required
@require_http_methods(['GET', 'POST'])
def video_settings(request):
    """Manage video streaming and DRM settings"""
    settings_obj, created = VideoSettings.objects.get_or_create(id=1)
    
    if request.method == 'POST':
        settings_obj.enable_drm = request.POST.get('enable_drm') == 'on'
        settings_obj.enable_watermark = request.POST.get('enable_watermark') == 'on'
        settings_obj.watermark_text = request.POST.get('watermark_text', '')
        settings_obj.default_quality = request.POST.get('default_quality', '720p')
        settings_obj.max_quality = request.POST.get('max_quality', '1080p')
        settings_obj.allow_download = request.POST.get('allow_download') == 'on'
        settings_obj.enable_speed_control = request.POST.get('enable_speed_control') == 'on'
        settings_obj.enable_adaptive_streaming = request.POST.get('enable_adaptive_streaming') == 'on'
        settings_obj.buffer_time = int(request.POST.get('buffer_time', 5))
        settings_obj.enable_offline_viewing = request.POST.get('enable_offline_viewing') == 'on'
        settings_obj.track_watch_time = request.POST.get('track_watch_time') == 'on'
        settings_obj.require_full_watch = request.POST.get('require_full_watch') == 'on'
        settings_obj.save()
        
        messages.success(request, "Video settings updated successfully.")
        return redirect('platformadmin:video_settings')
    
    context = get_context_data(request)
    context['settings'] = settings_obj
    
    return render(request, 'platformadmin/video_settings.html', context)


# ============================================================================
# PUSH NOTIFICATIONS
# ============================================================================

@platformadmin_required
def notification_management(request):
    """Manage push notifications"""
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    from apps.notifications.models import Notification
    notifications = Notification.objects.all()
    
    if type_filter:
        notifications = notifications.filter(notification_type=type_filter)
    
    if status_filter == 'sent':
        notifications = notifications.filter(is_sent=True)
    elif status_filter == 'pending':
        notifications = notifications.filter(is_sent=False)
    
    if search:
        notifications = notifications.filter(Q(title__icontains=search) | Q(message__icontains=search))
    
    # Pagination
    paginator = Paginator(notifications.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['notifications'] = page_obj.object_list
    context['type_filter'] = type_filter
    context['status_filter'] = status_filter
    context['search'] = search
    
    # Stats
    context['stats'] = {
        'total_sent': Notification.objects.filter(is_sent=True).count(),
        'delivered': Notification.objects.filter(is_read=False).count(),
        'read': Notification.objects.filter(is_read=True).count(),
        'pending': Notification.objects.filter(is_sent=False).count(),
    }
    
    return render(request, 'platformadmin/notification_management.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def send_bulk_notification(request):
    """Send bulk push notifications"""
    if request.method == 'POST':
        target_role = request.POST.get('target_role', 'all')
        title = request.POST.get('title')
        message = request.POST.get('message')
        
        # Get target users
        if target_role == 'all':
            users = User.objects.filter(is_active=True)
        else:
            users = User.objects.filter(role=target_role, is_active=True)
        
        # Create notifications
        notifications_created = 0
        for user in users:
            Notification.objects.create(
                user=user,
                notification_type='announcement',
                title=title,
                message=message
            )
            notifications_created += 1
        
        messages.success(request, f"Sent {notifications_created} notifications successfully.")
        return redirect('platformadmin:notification_management')
    
    context = get_context_data(request)
    
    # User counts for estimated reach
    context['user_counts'] = {
        'all': User.objects.filter(is_active=True).count(),
        'students': User.objects.filter(role='student', is_active=True).count(),
        'teachers': User.objects.filter(role='teacher', is_active=True).count(),
        'admins': User.objects.filter(is_superuser=True, is_active=True).count(),
    }
    
    # Last notification
    context['last_notification'] = Notification.objects.order_by('-created_at').first()
    
    return render(request, 'platformadmin/send_bulk_notification.html', context)


# cms_page_edit: restore edit handler for CMS pages
@platformadmin_required
@require_http_methods(['GET', 'POST'])
def cms_page_edit(request, page_id):
    """Edit existing CMS page"""
    page = get_object_or_404(CMSPage, id=page_id)

    if request.method == 'POST':
        page.title = request.POST.get('title', page.title)
        page.slug = request.POST.get('slug', page.slug)
        page.content = request.POST.get('content', page.content)
        page.status = request.POST.get('status', page.status)
        page.save()
        messages.success(request, f"Page '{page.title}' updated successfully.")
        return redirect('platformadmin:cms_management')

    context = get_context_data(request)
    context['page'] = page
    return render(request, 'platformadmin/cms_page_edit.html', context)


@platformadmin_required
@require_http_methods(['POST'])
def cms_page_delete(request, page_id):
    """Delete CMS page"""
    page = get_object_or_404(CMSPage, id=page_id)
    title = page.title
    page.delete()
    messages.success(request, f"Page '{title}' deleted successfully.")
    return redirect('platformadmin:cms_management')


# ============================================================================
# FAQ CRUD OPERATIONS
# ============================================================================

@platformadmin_required
@require_http_methods(['POST'])
def faq_create(request):
    """Create new FAQ"""
    from apps.platformadmin.forms import FAQForm
    form = FAQForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "FAQ created successfully.")
    else:
        messages.error(request, "Error creating FAQ. Please check your input.")
    return redirect('platformadmin:faq_management')


@platformadmin_required
@require_http_methods(['POST'])
def faq_edit(request, faq_id):
    """Edit FAQ"""
    faq = get_object_or_404(FAQ, id=faq_id)
    faq.question = request.POST.get('question')
    faq.answer = request.POST.get('answer')
    faq.category = request.POST.get('category')
    faq.order = int(request.POST.get('order', 0))
    faq.is_active = request.POST.get('is_active') == 'on'
    faq.save()
    messages.success(request, "FAQ updated successfully.")
    return redirect('platformadmin:faq_management')


@platformadmin_required
@require_http_methods(['POST'])
def faq_delete(request, faq_id):
    """Delete FAQ"""
    faq = get_object_or_404(FAQ, id=faq_id)
    faq.delete()
    messages.success(request, "FAQ deleted successfully.")
    return redirect('platformadmin:faq_management')


# ============================================================================
# ANNOUNCEMENT CRUD OPERATIONS
# ============================================================================

@platformadmin_required
@require_http_methods(['POST'])
def announcement_create(request):
    """Create new announcement"""
    from apps.platformadmin.forms import AnnouncementForm
    form = AnnouncementForm(request.POST)
    if form.is_valid():
        announcement = form.save(commit=False)
        announcement.created_by = request.user
        announcement.save()
        messages.success(request, "Announcement created successfully.")
    else:
        messages.error(request, "Error creating announcement. Please check your input.")
    return redirect('platformadmin:announcement_management')


@platformadmin_required
@require_http_methods(['POST'])
def announcement_edit(request, announcement_id):
    """Edit announcement"""
    announcement = get_object_or_404(Announcement, id=announcement_id)
    announcement.title = request.POST.get('title')
    announcement.message = request.POST.get('message')
    announcement.target_audience = request.POST.get('target_audience')
    announcement.priority = request.POST.get('priority')
    announcement.start_date = request.POST.get('start_date')
    announcement.end_date = request.POST.get('end_date') or None
    announcement.is_active = request.POST.get('is_active') == 'on'
    announcement.save()
    messages.success(request, "Announcement updated successfully.")
    return redirect('platformadmin:announcement_management')


@platformadmin_required
@require_http_methods(['POST'])
def announcement_delete(request, announcement_id):
    """Delete announcement"""
    announcement = get_object_or_404(Announcement, id=announcement_id)
    announcement.delete()
    messages.success(request, "Announcement deleted successfully.")
    return redirect('platformadmin:announcement_management')


# REFERRAL OPERATIONS removed: referral_complete view deleted
