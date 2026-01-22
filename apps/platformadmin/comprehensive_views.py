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
    VideoSettings, CourseAssignment, TeacherCommission, PayoutTransaction
)
from apps.courses.models import Course, Review, Enrollment
from apps.payments.models import Payment, Subscription, Coupon, CouponUsage
from apps.payments.commission_calculator import CommissionCalculator
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
    
    coupons = Coupon.objects.select_related('assigned_to_teacher').all()
    
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
        assigned_to_teacher_id = request.POST.get('assigned_to_teacher')
        
        try:
            # Determine creator_type and assigned_to_teacher
            creator_type = 'platform_admin'
            assigned_to_teacher = None
            
            if assigned_to_teacher_id:
                assigned_to_teacher = User.objects.get(id=assigned_to_teacher_id, role='teacher')
                creator_type = 'teacher'
            
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
                created_by=request.user,
                creator_type=creator_type,
                assigned_to_teacher=assigned_to_teacher
            )
            
            # Log action
            ActivityLog.log_action(
                request.user, 'create', 'Coupon', str(coupon.id), code,
                {}, {'code': code, 'discount': discount_value, 'teacher': assigned_to_teacher.email if assigned_to_teacher else 'Platform-wide'}
            )
            
            messages.success(request, f"Coupon '{code}' created successfully.")
            return redirect('platformadmin:coupon_management')
        
        except Exception as e:
            messages.error(request, f"Error creating coupon: {str(e)}")
    
    context = get_context_data(request)
    context['courses'] = Course.objects.filter(status='published')
    context['available_teachers'] = User.objects.filter(role='teacher', is_active=True).order_by('email')
    return render(request, 'platformadmin/coupon_create.html', context)


@platformadmin_required
@require_http_methods(['GET', 'POST'])
def coupon_edit(request, coupon_id):
    """Edit existing coupon"""
    coupon = get_object_or_404(Coupon, id=coupon_id)
    
    if request.method == 'POST':
        old_values = {
            'status': coupon.status,
            'discount_value': str(coupon.discount_value),
            'assigned_to_teacher': coupon.assigned_to_teacher.email if coupon.assigned_to_teacher else 'Platform-wide'
        }
        
        coupon.description = request.POST.get('description', '')
        coupon.status = request.POST.get('status', 'active')
        
        # Only update if provided
        if 'discount_value' in request.POST:
            coupon.discount_value = Decimal(request.POST['discount_value'])
        
        # Handle teacher assignment
        assigned_to_teacher_id = request.POST.get('assigned_to_teacher')
        if assigned_to_teacher_id:
            try:
                coupon.assigned_to_teacher = User.objects.get(id=assigned_to_teacher_id, role='teacher')
                coupon.creator_type = 'teacher'
            except User.DoesNotExist:
                messages.warning(request, "Selected teacher not found. Coupon remains platform-wide.")
        else:
            coupon.assigned_to_teacher = None
            coupon.creator_type = 'platform_admin'
        
        coupon.save()
        
        # Log action
        ActivityLog.log_action(
            request.user, 'update', 'Coupon', str(coupon.id), coupon.code,
            old_values, {
                'status': coupon.status, 
                'discount_value': str(coupon.discount_value),
                'assigned_to_teacher': coupon.assigned_to_teacher.email if coupon.assigned_to_teacher else 'Platform-wide'
            }
        )
        
        messages.success(request, f"Coupon '{coupon.code}' updated successfully.")
        return redirect('platformadmin:coupon_management')
    
    context = get_context_data(request)
    context['coupon'] = coupon
    context['available_teachers'] = User.objects.filter(role='teacher', is_active=True).order_by('email')
    context['usage_stats'] = {
        'total_uses': coupon.usages.count(),
        'unique_users': coupon.usages.values('user').distinct().count(),
        'total_discount': coupon.usages.aggregate(Sum('discount_amount'))['discount_amount__sum'] or 0,
        'total_revenue': coupon.usages.aggregate(Sum('final_amount'))['final_amount__sum'] or 0,
        'extra_commission': coupon.usages.aggregate(Sum('extra_commission_earned'))['extra_commission_earned__sum'] or 0,
    }
    
    # Recent usages
    context['recent_usages'] = coupon.usages.select_related('user', 'payment__course').order_by('-used_at')[:10]
    
    return render(request, 'platformadmin/coupon_edit.html', context)


@platformadmin_required
@platformadmin_required
@require_http_methods(['POST', 'GET'])
def coupon_delete(request, coupon_id):
    """Delete a coupon"""
    coupon = get_object_or_404(Coupon, id=coupon_id)
    
    if request.method == 'POST' or request.method == 'GET':
        coupon_code = coupon.code
        coupon_usage_count = coupon.usages.count()
        
        # Log action before deletion
        ActivityLog.log_action(
            request.user, 'delete', 'Coupon', str(coupon.id), coupon_code,
            {'code': coupon_code, 'status': coupon.status, 'usage_count': coupon_usage_count},
            {}
        )
        
        # Delete the coupon
        coupon.delete()
        
        messages.success(request, f"Coupon '{coupon_code}' has been deleted successfully. Note: Usage history is preserved for audit purposes.")
        return redirect('platformadmin:coupon_management')


@platformadmin_required
def coupon_statistics(request):
    """View detailed coupon statistics"""
    from decimal import Decimal
    
    # Overall stats
    total_coupons = Coupon.objects.count()
    active_coupons = Coupon.objects.filter(status='active').count()
    total_uses = CouponUsage.objects.count()
    total_discount = CouponUsage.objects.aggregate(Sum('discount_amount'))['discount_amount__sum'] or Decimal('0')
    total_revenue = CouponUsage.objects.aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0')
    total_extra_commission = CouponUsage.objects.aggregate(Sum('extra_commission_earned'))['extra_commission_earned__sum'] or Decimal('0')
    
    # Platform Admin vs Teacher coupons
    platform_coupons = Coupon.objects.filter(creator_type='platform_admin')
    teacher_coupons = Coupon.objects.filter(creator_type='teacher')
    
    platform_stats = {
        'count': platform_coupons.count(),
        'uses': CouponUsage.objects.filter(coupon__creator_type='platform_admin').count(),
        'revenue': CouponUsage.objects.filter(coupon__creator_type='platform_admin').aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0'),
        'extra_commission': CouponUsage.objects.filter(coupon__creator_type='platform_admin').aggregate(Sum('extra_commission_earned'))['extra_commission_earned__sum'] or Decimal('0'),
    }
    
    teacher_stats = {
        'count': teacher_coupons.count(),
        'uses': CouponUsage.objects.filter(coupon__creator_type='teacher').count(),
        'revenue': CouponUsage.objects.filter(coupon__creator_type='teacher').aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0'),
        'extra_commission': CouponUsage.objects.filter(coupon__creator_type='teacher').aggregate(Sum('extra_commission_earned'))['extra_commission_earned__sum'] or Decimal('0'),
    }
    
    # Top performing coupons
    top_coupons = Coupon.objects.annotate(
        usage_count=Count('usages'),
        total_revenue=Sum('usages__final_amount')
    ).order_by('-usage_count')[:10]
    
    context = get_context_data(request)
    context.update({
        'total_coupons': total_coupons,
        'active_coupons': active_coupons,
        'total_uses': total_uses,
        'total_discount': total_discount,
        'total_revenue': total_revenue,
        'total_extra_commission': total_extra_commission,
        'platform_stats': platform_stats,
        'teacher_stats': teacher_stats,
        'top_coupons': top_coupons,
    })
    
    return render(request, 'platformadmin/coupon_statistics.html', context)


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
    # Subscription management UI removed from platformadmin. Backend Subscription model remains.
    messages.info(request, "Subscription UI has been removed from the platform admin.")
    return redirect('platformadmin:dashboard')


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
    
    # Overall stats - calculate actual platform and teacher earnings
    all_completed_payments = Payment.objects.filter(status='completed').select_related('course')
    total_revenue = Decimal('0')
    total_platform_earnings = Decimal('0')
    total_instructor_earnings = Decimal('0')
    
    # Calculate accurate commission for each payment
    for payment in all_completed_payments:
        total_revenue += payment.amount
        
        # Get coupon usage if any
        coupon_usage = CouponUsage.objects.filter(payment=payment).first()
        coupon = coupon_usage.coupon if coupon_usage else None
        
        # Calculate commission using the commission calculator
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        total_platform_earnings += commission_data['platform_commission']
        total_instructor_earnings += commission_data['teacher_revenue']
    
    # Calculate per-teacher earnings using actual commission rates
    teachers_list = list(context['teachers'])
    for teacher in teachers_list:
        # Get all payments for this teacher's courses
        teacher_payments = Payment.objects.filter(
            course__teacher=teacher,
            status='completed'
        ).select_related('course')
        
        teacher_sales = Decimal('0')
        teacher_platform_commission = Decimal('0')
        teacher_net_earnings = Decimal('0')
        
        for payment in teacher_payments:
            teacher_sales += payment.amount
            
            # Get coupon usage if any
            coupon_usage = CouponUsage.objects.filter(payment=payment).first()
            coupon = coupon_usage.coupon if coupon_usage else None
            
            # Calculate commission using the commission calculator
            commission_data = CommissionCalculator.calculate_commission(payment, coupon)
            teacher_platform_commission += commission_data['platform_commission']
            teacher_net_earnings += commission_data['teacher_revenue']
        
        # Get teacher commission balance (paid out amounts)
        try:
            teacher_commission = TeacherCommission.objects.get(teacher=teacher)
            teacher.total_paid_out = teacher_commission.total_paid
            teacher.remaining_balance = teacher_commission.remaining_balance
        except TeacherCommission.DoesNotExist:
            teacher.total_paid_out = Decimal('0.00')
            teacher.remaining_balance = teacher_net_earnings
        
        # Set the calculated values on the teacher object
        teacher.total_sales = teacher_sales
        teacher.platform_commission = teacher_platform_commission
        teacher.net_earnings = teacher_net_earnings
        
        # Calculate teacher's average commission rate
        if teacher_sales > 0:
            teacher.commission_rate = (teacher_platform_commission / teacher_sales * 100).quantize(Decimal('0.01'))
        else:
            teacher.commission_rate = Decimal('0.00')

    # Calculate average platform commission percentage
    if total_revenue > 0:
        avg_platform_commission_pct = (total_platform_earnings / total_revenue * 100).quantize(Decimal('0.01'))
        avg_instructor_commission_pct = (total_instructor_earnings / total_revenue * 100).quantize(Decimal('0.01'))
    else:
        avg_platform_commission_pct = Decimal('0.00')
        avg_instructor_commission_pct = Decimal('0.00')

    context['earnings_stats'] = {
        'total_revenue': total_revenue,
        'platform_earnings': total_platform_earnings,
        'instructor_earnings': total_instructor_earnings,
        'platform_commission_pct': avg_platform_commission_pct,
        'instructor_commission_pct': avg_instructor_commission_pct,
        'pending_payouts': InstructorPayout.objects.filter(status='requested').count(),
    }
    
    return render(request, 'platformadmin/instructor_earnings.html', context)


@platformadmin_required
def payout_management(request):
    """Manage teacher commission payouts - manual settlement"""
    search = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-remaining')  # Default: highest remaining first
    
    # Get all teachers with commission balances
    teachers_with_commissions = TeacherCommission.objects.select_related('teacher').all()
    
    # Search filter
    if search:
        teachers_with_commissions = teachers_with_commissions.filter(
            Q(teacher__email__icontains=search) |
            Q(teacher__first_name__icontains=search) |
            Q(teacher__last_name__icontains=search)
        )
    
    # Calculate remaining balance for each and prepare data
    teacher_data = []
    for tc in teachers_with_commissions:
        remaining = tc.remaining_balance
        # Only show teachers with earnings
        if tc.total_earned > 0:
            teacher_data.append({
                'teacher_commission': tc,
                'teacher': tc.teacher,
                'total_earned': tc.total_earned,
                'total_paid': tc.total_paid,
                'remaining_balance': remaining,
            })
    
    # Sort
    if sort_by == '-remaining':
        teacher_data.sort(key=lambda x: x['remaining_balance'], reverse=True)
    elif sort_by == 'remaining':
        teacher_data.sort(key=lambda x: x['remaining_balance'])
    elif sort_by == '-earned':
        teacher_data.sort(key=lambda x: x['total_earned'], reverse=True)
    elif sort_by == 'name':
        teacher_data.sort(key=lambda x: x['teacher'].email)
    
    # Pagination
    paginator = Paginator(teacher_data, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['page_obj'] = page_obj
    context['teachers'] = page_obj.object_list
    context['search'] = search
    context['sort_by'] = sort_by
    
    # Calculate statistics
    total_pending = sum(t['remaining_balance'] for t in teacher_data)
    total_paid_overall = TeacherCommission.objects.aggregate(Sum('total_paid'))['total_paid__sum'] or 0
    teachers_with_pending = sum(1 for t in teacher_data if t['remaining_balance'] > 0)
    
    context['payout_stats'] = {
        'total_pending': total_pending,
        'total_paid_overall': total_paid_overall,
        'teachers_with_pending': teachers_with_pending,
        'total_teachers': len(teacher_data),
    }
    
    return render(request, 'platformadmin/payout_management.html', context)


@platformadmin_required
@require_POST
def payout_process(request):
    """Process manual payout to a teacher"""
    teacher_id = request.POST.get('teacher_id')
    amount_str = request.POST.get('amount', '0')
    payment_method = request.POST.get('payment_method', '')
    transaction_reference = request.POST.get('transaction_reference', '')
    admin_notes = request.POST.get('admin_notes', '')
    
    try:
        teacher = get_object_or_404(User, id=teacher_id, role='teacher')
        amount = Decimal(amount_str)
        
        # Validate amount
        if amount <= 0:
            messages.error(request, "Payout amount must be greater than zero.")
            return redirect('platformadmin:payout_management')
        
        # Get or create teacher commission record
        teacher_commission, created = TeacherCommission.objects.get_or_create(
            teacher=teacher
        )
        
        # Check if amount exceeds remaining balance
        remaining = teacher_commission.remaining_balance
        if amount > remaining:
            messages.error(
                request, 
                f"Payout amount (₹{amount}) exceeds remaining balance (₹{remaining}). Please enter a valid amount."
            )
            return redirect('platformadmin:payout_management')
        
        # Create payout transaction
        payout_transaction = PayoutTransaction.objects.create(
            teacher=teacher,
            amount=amount,
            status='completed',
            payment_method=payment_method,
            transaction_reference=transaction_reference,
            processed_by=request.user,
            processed_at=timezone.now(),
            admin_notes=admin_notes
        )
        
        # Update teacher commission balance
        teacher_commission.total_paid += amount
        teacher_commission.last_payout_at = timezone.now()
        teacher_commission.save()
        
        # Log the action
        ActivityLog.log_action(
            request.user, 
            'create', 
            'PayoutTransaction', 
            str(payout_transaction.id),
            f"Payout to {teacher.email} - ₹{amount}",
            {},
            {
                'amount': str(amount),
                'teacher': teacher.email,
                'remaining_after': str(teacher_commission.remaining_balance)
            }
        )
        
        messages.success(
            request, 
            f"Successfully paid ₹{amount} to {teacher.get_full_name() or teacher.email}. Remaining balance: ₹{teacher_commission.remaining_balance}"
        )
        
    except User.DoesNotExist:
        messages.error(request, "Teacher not found.")
    except ValueError:
        messages.error(request, "Invalid amount entered.")
    except Exception as e:
        messages.error(request, f"Error processing payout: {str(e)}")
    
    return redirect('platformadmin:payout_management')


@platformadmin_required
def payout_history(request, teacher_id):
    """View payout history for a specific teacher"""
    teacher = get_object_or_404(User, id=teacher_id, role='teacher')
    
    # Get teacher commission record
    try:
        teacher_commission = TeacherCommission.objects.get(teacher=teacher)
    except TeacherCommission.DoesNotExist:
        teacher_commission = None
    
    # Get all payout transactions
    transactions = PayoutTransaction.objects.filter(
        teacher=teacher
    ).select_related('processed_by').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_context_data(request)
    context['teacher'] = teacher
    context['teacher_commission'] = teacher_commission
    context['page_obj'] = page_obj
    context['transactions'] = page_obj.object_list
    
    return render(request, 'platformadmin/payout_history.html', context)


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
    # Student progress UI removed from platformadmin. Keep backend data/models intact.
    messages.info(request, "Student progress UI has been removed from the platform admin.")
    return redirect('platformadmin:dashboard')


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
    # Video settings UI removed from platformadmin. Backend model `VideoSettings` remains.
    messages.info(request, "Video settings UI has been removed from the platform admin.")
    return redirect('platformadmin:dashboard')


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
