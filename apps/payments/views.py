"""
Payment views for Razorpay integration
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.conf import settings
import json
import logging
from .models import Payment, Subscription, PaymentWebhook
from .utils import RazorpayHandler, convert_to_paise, convert_from_paise
from apps.courses.models import Course, Enrollment

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
    
    # Create Razorpay order
    razorpay_handler = RazorpayHandler()
    order = razorpay_handler.create_order(
        amount=course.price,
        receipt=f'course_{course.id}_user_{request.user.id}',
        notes={
            'course_id': course.id,
            'course_title': course.title,
            'user_id': request.user.id,
            'user_email': request.user.email
        }
    )
    
    if not order:
        messages.error(request, 'Failed to create payment order. Please try again.')
        return redirect('courses:course_detail', slug=course.slug)
    
    # Create payment record
    payment = Payment.objects.create(
        user=request.user,
        course=course,
        amount=course.price,
        currency='INR',
        razorpay_order_id=order['id'],
        status='pending'
    )
    
    context = {
        'course': course,
        'payment': payment,
        'order': order,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'user': request.user,
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
    
    context = {
        'payments': payments
    }
    
    return render(request, 'payments/my_payments.html', context)


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
