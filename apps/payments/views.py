"""
Payment views for Razorpay integration
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.db import models
import json
from .models import Payment, Subscription, PaymentWebhook, CouponUsage, Coupon
from .utils import RazorpayHandler, convert_to_paise, convert_from_paise
from .commission_calculator import CommissionCalculator
from apps.courses.models import Course, Enrollment
from django.db.models import Sum
from decimal import Decimal

logger = logging.getLogger(__name__)


@login_required
def course_payment(request, course_id):
    """Initiate payment for a course"""
    course = get_object_or_404(Course, id=course_id, status='published')
    
    # Check if already enrolled
    if Enrollment.objects.filter(student=request.user, course=course, status='active').exists():
        messages.info(request, 'You are already enrolled in this course!')
        return redirect('courses:course_detail', slug=course.slug)
    
    if course.price == 0:
        messages.info(request, 'This is a free course!')
        return redirect('courses:enroll_course', course_id=course.id)
    
    # Determine base amount (use discounted/actual price if present)
    if getattr(course, 'actual_price', None):
        base_amount = course.actual_price
    else:
        base_amount = course.price

    # Handle coupon code
    coupon_code = request.GET.get('coupon') or request.POST.get('coupon')
    applied_coupon = None
    original_amount = base_amount
    discount_amount = Decimal('0')
    final_amount = base_amount
    
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code, status='active')
            is_valid, message = coupon.is_valid()
            
            if is_valid:
                # Check course applicability
                if coupon.applicable_courses.exists() and course not in coupon.applicable_courses.all():
                    messages.warning(request, 'This coupon is not applicable to this course.')
                elif coupon.applicable_categories.exists() and course.category not in coupon.applicable_categories.all():
                    messages.warning(request, 'This coupon is not applicable to this course category.')
                elif base_amount < coupon.min_purchase_amount:
                    messages.warning(request, f'Minimum purchase amount of ₹{coupon.min_purchase_amount} required for this coupon.')
                else:
                    # Check user usage limit
                    user_usage_count = CouponUsage.objects.filter(coupon=coupon, user=request.user).count()
                    if user_usage_count >= coupon.max_uses_per_user:
                        messages.warning(request, 'You have already used this coupon the maximum number of times.')
                    else:
                        # Apply discount
                        discount_amount = Decimal(str(coupon.calculate_discount(base_amount)))
                        final_amount = base_amount - discount_amount
                        applied_coupon = coupon
                        messages.success(request, f'Coupon applied! You saved ₹{discount_amount}')
            else:
                messages.warning(request, message)
        except Coupon.DoesNotExist:
            messages.error(request, 'Invalid coupon code.')
    
    # Create Razorpay order with final amount
    razorpay_handler = RazorpayHandler()
    order = razorpay_handler.create_order(
        amount=final_amount,
        receipt=f'course_{course.id}_user_{request.user.id}',
        notes={
            'course_id': course.id,
            'course_title': course.title,
            'user_id': request.user.id,
            'user_email': request.user.email,
            'coupon_code': coupon_code if applied_coupon else '',
            'original_amount': str(original_amount),
            'discount_amount': str(discount_amount)
        }
    )
    
    if not order:
        messages.error(request, 'Failed to create payment order. Please try again.')
        return redirect('courses:course_detail', slug=course.slug)
    
    # Create payment record
    payment = Payment.objects.create(
        user=request.user,
        course=course,
        amount=final_amount,
        currency='INR',
        razorpay_order_id=order['id'],
        status='pending'
    )
    
    # Store coupon info in session for later use
    if applied_coupon:
        request.session[f'coupon_{payment.razorpay_order_id}'] = {
            'code': applied_coupon.code,
            'original_amount': str(original_amount),
            'discount_amount': str(discount_amount),
            'final_amount': str(final_amount)
        }
    
    context = {
        'course': course,
        'payment': payment,
        'order': order,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'user': request.user,
        'applied_coupon': applied_coupon,
        'original_amount': original_amount,
        'discount_amount': discount_amount,
        'final_amount': final_amount,
    }
    
    return render(request, 'payments/course_payment.html', context)


@login_required
def verify_payment(request):
    """Verify Razorpay payment signature and fetch payment details"""
    if request.method == 'POST':
        data = json.loads(request.body)
        
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')
        
        # Get payment record
        payment = get_object_or_404(Payment, razorpay_order_id=razorpay_order_id, user=request.user)
        
        # Verify signature
        razorpay_handler = RazorpayHandler()
        is_valid = razorpay_handler.verify_payment_signature(
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature
        )
        
        if is_valid:
            # Fetch payment details from Razorpay to get payment method info
            payment_details = razorpay_handler.fetch_payment(razorpay_payment_id)
            
            # Update payment
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature
            payment.status = 'completed'
            
            # Extract and encrypt payment method details
            if payment_details:
                payment_method = payment_details.get('method', '')
                payment.payment_method = payment_method
                
                # Encrypt sensitive payment method information (256-bit AES)
                if payment_method == 'card':
                    card_info = payment_details.get('card', {})
                    payment.set_card_details(
                        last4=card_info.get('last4'),
                        card_type=card_info.get('network')  # Visa, Mastercard, etc.
                    )
                elif payment_method == 'upi':
                    upi_info = payment_details.get('vpa')  # Virtual Payment Address
                    if upi_info:
                        payment.set_upi_id(upi_info)
                elif payment_method == 'wallet':
                    wallet_info = payment_details.get('wallet')
                    if wallet_info:
                        payment.set_wallet_name(wallet_info)
                elif payment_method == 'netbanking':
                    bank_info = payment_details.get('bank')
                    if bank_info:
                        payment.set_bank_name(bank_info)
            
            from django.utils import timezone
            payment.completed_at = timezone.now()
            payment.save()
            
            # Check if coupon was used and record usage
            coupon_usage = None
            coupon_data = request.session.get(f'coupon_{razorpay_order_id}')
            
            if coupon_data:
                try:
                    coupon = Coupon.objects.get(code=coupon_data['code'])
                    
                    # Create coupon usage record
                    original_amount = Decimal(coupon_data['original_amount'])
                    discount_amount = Decimal(coupon_data['discount_amount'])
                    final_amount = Decimal(coupon_data['final_amount'])
                    
                    # Determine commission recipient
                    commission_recipient = None
                    extra_commission = Decimal('0')
                    
                    if coupon.creator_type == 'teacher' and coupon.assigned_to_teacher:
                        commission_recipient = coupon.assigned_to_teacher
                        extra_commission = discount_amount  # Teacher gets the discount amount as extra commission
                    elif coupon.creator_type == 'platform_admin':
                        # Platform admin gets the commission
                        if coupon.created_by:
                            commission_recipient = coupon.created_by
                        extra_commission = discount_amount
                    
                    coupon_usage = CouponUsage.objects.create(
                        coupon=coupon,
                        user=request.user,
                        payment=payment,
                        original_amount=original_amount,
                        discount_amount=discount_amount,
                        final_amount=final_amount,
                        extra_commission_earned=extra_commission,
                        commission_recipient=commission_recipient
                    )
                    
                    # Increment coupon usage count
                    coupon.current_uses += 1
                    coupon.save()
                    
                    # Clear session data
                    del request.session[f'coupon_{razorpay_order_id}']
                    
                    logger.info(f"Coupon {coupon.code} applied to payment {payment.id}")
                except Coupon.DoesNotExist:
                    logger.warning(f"Coupon not found: {coupon_data['code']}")
                except Exception as e:
                    logger.error(f"Error recording coupon usage: {str(e)}")
            
            # Calculate and record commission distribution
            commission_data = CommissionCalculator.record_commission_on_payment(payment, coupon_usage)
            
            logger.info(f"Commission calculated - Scenario: {commission_data['scenario']}, "
                       f"Platform: {commission_data['platform_commission']}, "
                       f"Teacher: {commission_data['teacher_revenue']}, "
                       f"Extra: {commission_data['extra_commission']}")
            
            # Create enrollment and unlock course
            enrollment, created = Enrollment.objects.get_or_create(
                student=request.user,
                course=payment.course,
                defaults={
                    'status': 'active',
                    'payment_amount': payment.amount,
                    'payment_reference': str(payment.id)
                }
            )
            
            # Update enrollment if it already existed
            if not created and enrollment.status != 'active':
                enrollment.status = 'active'
                enrollment.payment_amount = payment.amount
                enrollment.payment_reference = str(payment.id)
                enrollment.save()
            
            logger.info(f"Payment successful: {payment.id} - Course unlocked for user {request.user.id}")
            
            return JsonResponse({
                'status': 'success',
                'payment_id': str(payment.id),
                'message': 'Payment successful! Course unlocked.',
                'redirect_url': f'/courses/{payment.course.slug}/'
            })
        else:
            payment.status = 'failed'
            payment.failure_reason = 'Payment signature verification failed'
            payment.save()
            
            logger.warning(f"Payment verification failed: {payment.id}")
            
            return JsonResponse({
                'status': 'failed',
                'message': 'Payment verification failed!'
            }, status=400)
    
    return JsonResponse({'success': False}, status=400)


@csrf_exempt
def razorpay_webhook(request):
    """Handle Razorpay webhooks"""
    if request.method == 'POST':
        # Get signature from headers
        signature = request.headers.get('X-Razorpay-Signature')
        
        # Verify webhook signature
        razorpay_handler = RazorpayHandler()
        is_valid = razorpay_handler.verify_webhook_signature(request.body, signature)
        
        if not is_valid:
            logger.warning('Invalid webhook signature')
            return HttpResponse(status=400)
        
        # Parse webhook data
        data = json.loads(request.body)
        event = data.get('event')
        payload = data.get('payload', {})
        
        # Log webhook
        PaymentWebhook.objects.create(
            event_type=event,
            payload=data,
            processed=False
        )
        
        # Handle different events
        if event == 'payment.captured':
            payment_entity = payload.get('payment', {}).get('entity', {})
            payment_id = payment_entity.get('id')
            order_id = payment_entity.get('order_id')
            
            try:
                payment = Payment.objects.get(razorpay_order_id=order_id)
                payment.razorpay_payment_id = payment_id
                payment.status = 'completed'
                
                # Extract and encrypt payment method details
                payment_method = payment_entity.get('method', '')
                payment.payment_method = payment_method
                
                if payment_method == 'card':
                    card_info = payment_entity.get('card', {})
                    payment.set_card_details(
                        last4=card_info.get('last4'),
                        card_type=card_info.get('network')
                    )
                elif payment_method == 'upi':
                    upi_info = payment_entity.get('vpa')
                    if upi_info:
                        payment.set_upi_id(upi_info)
                elif payment_method == 'wallet':
                    wallet_info = payment_entity.get('wallet')
                    if wallet_info:
                        payment.set_wallet_name(wallet_info)
                elif payment_method == 'netbanking':
                    bank_info = payment_entity.get('bank')
                    if bank_info:
                        payment.set_bank_name(bank_info)
                
                from django.utils import timezone
                payment.completed_at = timezone.now()
                payment.save()
                
                # Create enrollment if not exists and unlock course
                Enrollment.objects.get_or_create(
                    student=payment.user,
                    course=payment.course,
                    defaults={
                        'status': 'active',
                        'payment_amount': payment.amount,
                        'payment_reference': str(payment.id)
                    }
                )
                
                logger.info(f"Webhook processed: payment captured {payment_id} - Course unlocked")
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for order: {order_id}")
        
        elif event == 'payment.failed':
            payment_entity = payload.get('payment', {}).get('entity', {})
            order_id = payment_entity.get('order_id')
            
            try:
                payment = Payment.objects.get(razorpay_order_id=order_id)
                payment.status = 'failed'
                payment.save()
                
                logger.info(f"Webhook processed: payment failed {order_id}")
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for order: {order_id}")
        
        elif event == 'refund.created':
            refund_entity = payload.get('refund', {}).get('entity', {})
            payment_id = refund_entity.get('payment_id')
            refund_id = refund_entity.get('id')
            amount = refund_entity.get('amount')
            
            try:
                payment = Payment.objects.get(razorpay_payment_id=payment_id)
                
                from .models import Refund
                Refund.objects.create(
                    payment=payment,
                    amount=convert_from_paise(amount),
                    razorpay_refund_id=refund_id,
                    status='processing'
                )
                
                logger.info(f"Webhook processed: refund created {refund_id}")
            except Payment.DoesNotExist:
                logger.error(f"Payment not found: {payment_id}")
        
        return HttpResponse(status=200)
    
    return HttpResponse(status=400)


@login_required
def payment_success(request):
    """Payment success page"""
    payment_id = request.GET.get('payment_id')
    
    if payment_id:
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)
        context = {
            'payment': payment,
            'course': payment.course
        }
        return render(request, 'payments/payment_success.html', context)
    
    return redirect('users:dashboard')


@login_required
def payment_failed(request):
    """Payment failed page"""
    payment_id = request.GET.get('payment_id')
    
    if payment_id:
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)
        context = {
            'payment': payment,
            'course': payment.course
        }
        return render(request, 'payments/payment_failed.html', context)
    
    return redirect('users:dashboard')


@login_required
def my_payments(request):
    """List user's payment history"""
    payments = Payment.objects.filter(user=request.user).select_related('course').order_by('-created_at')
    
    # Calculate stats
    total_payments = payments.count()
    completed_payments = payments.filter(status='completed')
    successful_payments = completed_payments.count()
    total_spent = completed_payments.aggregate(total=models.Sum('amount'))['total'] or 0
    
    context = {
        'payments': payments,
        'total_payments': total_payments,
        'successful_payments': successful_payments,
        'total_spent': total_spent,
    }
    
    return render(request, 'payments/my_payments.html', context)


@login_required
def teacher_earnings(request):
    """Teacher-facing earnings view: sums sales for courses taught by the current user and
    calculates accurate commission using CommissionCalculator.
    """
    from apps.payments.commission_calculator import CommissionCalculator
    
    user = request.user

    # Get all payments for this teacher's courses
    teacher_payments = Payment.objects.filter(
        course__teacher=user,
        status='completed'
    ).select_related('course').order_by('-completed_at')

    total_sales = Decimal('0')
    platform_commission = Decimal('0')
    base_earnings = Decimal('0')
    extra_commission = Decimal('0')

    # Calculate accurate commission for each payment
    for payment in teacher_payments:
        total_sales += payment.amount
        
        # Get coupon usage if any
        coupon_usage = CouponUsage.objects.filter(payment=payment).first()
        coupon = coupon_usage.coupon if coupon_usage else None
        
        # Calculate commission using the commission calculator
        commission_data = CommissionCalculator.calculate_commission(payment, coupon)
        platform_commission += commission_data['platform_commission']
        
        # Track extra commission separately for display
        if commission_data['extra_commission'] > 0 and commission_data['extra_commission_recipient'] == user:
            extra_commission += commission_data['extra_commission']
            # Base earnings is teacher revenue minus extra commission
            base_earnings += (commission_data['teacher_revenue'] - commission_data['extra_commission'])
        else:
            base_earnings += commission_data['teacher_revenue']

    net_earnings = base_earnings + extra_commission

    # Recent transactions (limited to 20)
    recent_payments = teacher_payments[:20]

    context = {
        'total_sales': total_sales,
        'platform_commission': platform_commission,
        'base_teacher_earnings': base_earnings,
        'extra_commission': extra_commission,
        'net_earnings': net_earnings,
        'recent_payments': recent_payments,
    }

    return render(request, 'payments/teacher_earnings.html', context)


@login_required
def request_refund(request, payment_id):
    """Request a refund for a payment"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user, status='completed')
    
    # Check if refund already exists
    from .models import Refund
    if Refund.objects.filter(payment=payment).exists():
        messages.warning(request, 'A refund request already exists for this payment.')
        return redirect('payments:my_payments')
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        
        # Create refund via Razorpay
        razorpay_handler = RazorpayHandler()
        refund = razorpay_handler.refund_payment(
            payment.razorpay_payment_id,
            notes={'reason': reason}
        )
        
        if refund:
            # Create refund record
            Refund.objects.create(
                payment=payment,
                amount=payment.amount,
                reason=reason,
                razorpay_refund_id=refund['id'],
                status='processing'
            )
            
            messages.success(request, 'Refund request submitted successfully!')
        else:
            messages.error(request, 'Failed to process refund. Please contact support.')
        
        return redirect('payments:my_payments')
    
    context = {
        'payment': payment
    }
    
    return render(request, 'payments/request_refund.html', context)


@login_required

def validate_coupon(request):

    if request.method == 'POST':
        data = json.loads(request.body)
        coupon_code = data.get('coupon_code', '').strip()
        course_id = data.get('course_id')
        
        if not coupon_code:
            return JsonResponse({'valid': False, 'message': 'Please enter a coupon code.'})
        
        if not course_id:
            return JsonResponse({'valid': False, 'message': 'Course not specified.'})
        
        try:
            course = Course.objects.get(id=course_id, status='published')
        except Course.DoesNotExist:
            return JsonResponse({'valid': False, 'message': 'Course not found.'})
        
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code, status='active')
        except Coupon.DoesNotExist:
            return JsonResponse({'valid': False, 'message': 'Invalid coupon code.'})
        
        # Check coupon validity
        is_valid, message = coupon.is_valid()
        if not is_valid:
            return JsonResponse({'valid': False, 'message': message})
        
        # Check course applicability
        if coupon.applicable_courses.exists() and course not in coupon.applicable_courses.all():
            return JsonResponse({'valid': False, 'message': 'This coupon is not applicable to this course.'})
        
        if coupon.applicable_categories.exists() and course.category not in coupon.applicable_categories.all():
            return JsonResponse({'valid': False, 'message': 'This coupon is not applicable to this course category.'})
        
        if course.price < coupon.min_purchase_amount:
            return JsonResponse({
                'valid': False, 
                'message': f'Minimum purchase amount of ₹{coupon.min_purchase_amount} required for this coupon.'
            })
        
        # Check user usage limit
        user_usage_count = CouponUsage.objects.filter(coupon=coupon, user=request.user).count()
        if user_usage_count >= coupon.max_uses_per_user:
            return JsonResponse({'valid': False, 'message': 'You have already used this coupon the maximum number of times.'})
        
        # Calculate discount
        discount_amount = coupon.calculate_discount(course.price)
        final_amount = course.price - Decimal(str(discount_amount))
        
        return JsonResponse({
            'valid': True,
            'message': f'Coupon applied! You save ₹{discount_amount}',
            'discount_amount': float(discount_amount),
            'final_amount': float(final_amount),
            'original_amount': float(course.price),
            'discount_type': coupon.discount_type,
            'discount_value': float(coupon.discount_value)
        })
    
    return JsonResponse({'valid': False, 'message': 'Invalid request.'}, status=400)
