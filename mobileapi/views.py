"""
Views and ViewSets for Mobile API
RESTful endpoints optimized for React Native mobile app
"""
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q, Count, Avg, F, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from django.core.mail import send_mail
from django.conf import settings
import logging

from apps.courses.models import (
    Course, Category, Module, Lesson, 
    Enrollment, LessonProgress, Review
)
from apps.common.models import Banner
from apps.notifications.models import Notification
from apps.payments.models import Payment, Subscription
from apps.analytics.models import ListeningSession

from .serializers import (
    UserProfileSerializer, UserRegistrationSerializer,
    CategorySerializer, CourseListSerializer, CourseDetailSerializer,
    ModuleSerializer, LessonListSerializer, LessonDetailSerializer,
    EnrollmentSerializer, EnrollmentDetailSerializer,
    LessonProgressSerializer, ReviewSerializer,
    NotificationSerializer, PaymentSerializer, SubscriptionSerializer,
    ListeningSessionSerializer, MobileBannerSerializer,
    CourseSearchSerializer,
)

logger = logging.getLogger(__name__)


User = get_user_model()


# ============================================================================
# Authentication Views
# ============================================================================

class LoginView(APIView):
    """Mobile login endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(email=email, password=password)
        
        if user:
            # Check if email is verified
            if not user.email_verified:
                return Response({
                    'error': 'Please verify your email first',
                    'requires_verification': True,
                    'user_id': user.id,
                    'email': user.email
                }, status=status.HTTP_403_FORBIDDEN)
            
            if not user.is_active:
                return Response(
                    {'error': 'Account is inactive'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get or create token
            token, created = Token.objects.get_or_create(user=user)
            
            # Serialize user data
            serializer = UserProfileSerializer(user, context={'request': request})
            
            return Response({
                'token': token.key,
                'user': serializer.data,
            })
        
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )


class RegisterView(APIView):
    """Mobile registration endpoint - creates user and sends OTP for verification"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            # Create user but keep inactive until email is verified
            user = serializer.save()
            user.is_active = False  # User cannot login until email verified
            user.email_verified = False
            user.save()
            
            # Send OTP for email verification
            from apps.users.otp_utils import send_otp_email
            success, message, device = send_otp_email(user, purpose='verification', request=request)
            
            if success:
                return Response({
                    'message': 'Registration successful. Please verify your email with the OTP sent.',
                    'user_id': user.id,
                    'email': user.email,
                    'requires_verification': True
                }, status=status.HTTP_201_CREATED)
            else:
                # If OTP sending fails, delete the user and return error
                user.delete()
                return Response({
                    'error': f'Failed to send verification email: {message}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifySignupOTPView(APIView):
    """Verify email OTP after signup"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        otp = request.data.get('otp')
        
        if not user_id or not otp:
            return Response(
                {'error': 'User ID and OTP are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
            
            # Verify OTP
            from apps.users.otp_utils import verify_otp
            success, message = verify_otp(user, otp, purpose='verification', request=request)
            
            if success:
                # Mark email as verified and activate user
                user.email_verified = True
                user.is_active = True
                user.save()
                
                # Create token for automatic login
                token, created = Token.objects.get_or_create(user=user)
                
                # Serialize user data
                user_serializer = UserProfileSerializer(user, context={'request': request})
                
                return Response({
                    'message': 'Email verified successfully',
                    'token': token.key,
                    'user': user_serializer.data,
                })
            else:
                return Response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class ResendSignupOTPView(APIView):
    """Resend verification OTP"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        email = request.data.get('email')
        
        if not user_id and not email:
            return Response(
                {'error': 'User ID or email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if user_id:
                user = User.objects.get(id=user_id)
            else:
                user = User.objects.get(email=email)
            
            # Check if already verified
            if user.email_verified:
                return Response(
                    {'error': 'Email is already verified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Send OTP
            from apps.users.otp_utils import send_otp_email
            success, message, device = send_otp_email(user, purpose='verification', request=request)
            
            if success:
                return Response({
                    'message': 'Verification OTP has been resent to your email'
                })
            else:
                return Response(
                    {'error': message},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )



class LogoutView(APIView):
    """Mobile logout endpoint"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Delete the user's token
        request.user.auth_token.delete()
        return Response({'message': 'Successfully logged out'})


class ChangePasswordView(APIView):
    """Change password endpoint"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not old_password or not new_password:
            return Response(
                {'error': 'Both old and new passwords are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.user.check_password(old_password):
            return Response(
                {'error': 'Old password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(new_password) < 8:
            return Response(
                {'error': 'New password must be at least 8 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        request.user.set_password(new_password)
        request.user.save()
        
        return Response({'message': 'Password changed successfully'})


class ForgotPasswordView(APIView):
    """Send password reset email with OTP or reset link"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response(
                {'error': 'Email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            
            # For mobile API, we'll use the OTP system from the web app
            from apps.users.otp_utils import send_otp_email
            
            success, message, device = send_otp_email(user, purpose='password_reset', request=request)
            
            if success:
                return Response({
                    'message': 'Password reset OTP has been sent to your email',
                    'email': email
                })
            else:
                return Response(
                    {'error': message},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except User.DoesNotExist:
            # For security, don't reveal that email doesn't exist
            return Response({
                'message': 'If an account with this email exists, you will receive a password reset OTP'
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyResetOTPView(APIView):
    """Verify OTP for password reset"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        
        if not email or not otp:
            return Response(
                {'error': 'Email and OTP are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            
            from apps.users.otp_utils import verify_otp
            
            success, message = verify_otp(user, otp, purpose='password_reset', request=request)
            
            if success:
                # Generate a temporary token for password reset
                from django.contrib.auth.tokens import default_token_generator
                reset_token = default_token_generator.make_token(user)
                
                return Response({
                    'message': 'OTP verified successfully',
                    'reset_token': reset_token,
                    'user_id': user.id
                })
            else:
                return Response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid email'},
                status=status.HTTP_404_NOT_FOUND
            )


class ResetPasswordView(APIView):
    """Reset password with verified OTP token"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        reset_token = request.data.get('reset_token')
        new_password = request.data.get('new_password')
        
        if not all([user_id, reset_token, new_password]):
            return Response(
                {'error': 'User ID, reset token, and new password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(new_password) < 8:
            return Response(
                {'error': 'New password must be at least 8 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
            
            from django.contrib.auth.tokens import default_token_generator
            
            if default_token_generator.check_token(user, reset_token):
                user.set_password(new_password)
                user.save()
                
                # Delete any remaining OTP devices
                from apps.users.otp_utils import delete_user_otp_devices
                delete_user_otp_devices(user, 'password_reset')
                
                return Response({'message': 'Password reset successfully'})
            else:
                return Response(
                    {'error': 'Invalid or expired reset token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ============================================================================
# User Profile Views
# ============================================================================

class UserProfileView(APIView):
    """Get and update user profile"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)
    
    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Course ViewSets
# ============================================================================

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Category listing for browsing"""
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """Course listing and details"""
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'level', 'is_free', 'is_featured']
    search_fields = ['title', 'description', 'short_description']
    ordering_fields = ['created_at', 'price', 'average_rating', 'total_enrollments']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get published courses"""
        queryset = Course.objects.filter(status='published').select_related(
            'teacher', 'category'
        ).prefetch_related('modules__lessons')
        
        # Filter by teacher
        teacher_id = self.request.query_params.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseListSerializer
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured courses"""
        courses = self.get_queryset().filter(is_featured=True)[:10]
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending courses (most enrollments)"""
        courses = self.get_queryset().order_by('-total_enrollments')[:10]
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def top_rated(self, request):
        """Get top-rated courses"""
        courses = self.get_queryset().filter(
            total_reviews__gte=5
        ).order_by('-average_rating')[:10]
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get course reviews"""
        course = self.get_object()
        reviews = Review.objects.filter(course=course, is_approved=True).select_related('student')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def enroll(self, request, pk=None):
        """Enroll in a course"""
        course = self.get_object()
        
        # Check if already enrolled
        existing_enrollment = Enrollment.objects.filter(
            student=request.user,
            course=course,
            status__in=['active', 'completed']
        ).first()
        
        if existing_enrollment:
            return Response(
                {'error': 'Already enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is a free user or course is free
        is_free_user = request.user.is_free_user
        payment_amount = 0 if (course.actual_price == 0 or is_free_user) else course.actual_price
        
        # Create enrollment
        enrollment = Enrollment.objects.create(
            student=request.user,
            course=course,
            payment_amount=payment_amount
        )
        
        serializer = EnrollmentSerializer(enrollment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    """Lesson details and access"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get lessons user has access to"""
        return Lesson.objects.filter(
            is_published=True
        ).select_related('module', 'course')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LessonDetailSerializer
        return LessonListSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Get lesson details with enrollment check"""
        lesson = self.get_object()
        
        # Check if user has access
        if not lesson.is_free_preview:
            enrollment = Enrollment.objects.filter(
                student=request.user,
                course=lesson.course,
                status__in=['active', 'completed']
            ).first()
            
            if not enrollment:
                return Response(
                    {'error': 'You must be enrolled to access this lesson'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Pass enrollment to serializer context
            self.kwargs['enrollment'] = enrollment
        
        serializer = self.get_serializer(lesson)
        return Response(serializer.data)
    
    def get_serializer_context(self):
        """Add enrollment to context"""
        context = super().get_serializer_context()
        if hasattr(self, 'kwargs') and 'enrollment' in self.kwargs:
            context['enrollment'] = self.kwargs['enrollment']
        return context
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """Update lesson progress"""
        lesson = self.get_object()
        
        # Get enrollment
        enrollment = Enrollment.objects.filter(
            student=request.user,
            course=lesson.course,
            status__in=['active', 'completed']
        ).first()
        
        if not enrollment:
            return Response(
                {'error': 'Not enrolled in this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get or create progress
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson
        )
        
        # Update progress
        last_position = request.data.get('last_position_seconds', progress.last_position_seconds)
        # Accept either 'completion_percentage' (server-side name) or 'progress_percentage' (client alias)
        completion_percentage = request.data.get(
            'completion_percentage',
            request.data.get('progress_percentage', progress.completion_percentage)
        )
        is_completed = request.data.get('is_completed', progress.is_completed)
        
        progress.last_position_seconds = last_position
        progress.completion_percentage = completion_percentage
        
        if is_completed and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
        
        progress.save()
        
        # Update enrollment progress (if method exists)
        if hasattr(enrollment, 'update_progress'):
            enrollment.update_progress()
        
        serializer = LessonProgressSerializer(progress)
        return Response(serializer.data)


# ============================================================================
# Enrollment Views
# ============================================================================

class EnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    """User's course enrollments"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EnrollmentSerializer
    
    def get_queryset(self):
        """Get user's enrollments"""
        return Enrollment.objects.filter(
            student=self.request.user
        ).select_related('course').order_by('-enrolled_at')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EnrollmentDetailSerializer
        return EnrollmentSerializer
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active enrollments"""
        enrollments = self.get_queryset().filter(status='active')
        serializer = self.get_serializer(enrollments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def completed(self, request):
        """Get completed enrollments"""
        enrollments = self.get_queryset().filter(status='completed')
        serializer = self.get_serializer(enrollments, many=True)
        return Response(serializer.data)


# ============================================================================
# Review Views
# ============================================================================

class ReviewViewSet(viewsets.ModelViewSet):
    """Course reviews"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReviewSerializer
    
    def get_queryset(self):
        """Get user's reviews"""
        return Review.objects.filter(student=self.request.user)
    
    def perform_create(self, serializer):
        """Create review with current user"""
        # Check if user is enrolled
        course = serializer.validated_data['course']
        enrollment = Enrollment.objects.filter(
            student=self.request.user,
            course=course
        ).first()
        
        if not enrollment:
            return Response(
                {'error': 'You must be enrolled to review this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Save review with enrollment
        serializer.save(
            student=self.request.user,
            enrollment=enrollment
        )


# ============================================================================
# Notification Views
# ============================================================================

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """User notifications"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        """Get user's notifications"""
        return Notification.objects.filter(
            user=self.request.user
        ).select_related('course', 'lesson').order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications"""
        notifications = self.get_queryset().filter(is_read=False)
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'message': 'All notifications marked as read'})


# ============================================================================
# Payment & Subscription Views
# ============================================================================

class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """User payments"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer
    
    def get_queryset(self):
        """Get user's payments"""
        return Payment.objects.filter(user=self.request.user).order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def create_order(self, request):
        """Create Razorpay payment order"""
        from apps.payments.utils import create_razorpay_order
        
        course_id = request.data.get('course_id')
        if not course_id:
            return Response(
                {'error': 'Course ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            course = Course.objects.get(id=course_id, status='published')
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already enrolled
        if Enrollment.objects.filter(student=request.user, course=course, status='active').exists():
            return Response(
                {'error': 'Already enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is a free user
        if request.user.is_free_user:
            return Response(
                {'error': 'You have free access to this course. Use the enroll endpoint directly.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if course is free
        if course.actual_price == 0:
            return Response(
                {'error': 'This is a free course. Use the enroll endpoint directly.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # First, create a temporary payment object (not saved to DB yet)
        # to generate receipt and notes
        import time
        timestamp = int(time.time())
        temp_payment_id = f"{request.user.id}_{course.id}_{timestamp}"
        receipt = f'pay_{timestamp}'[:40]  # Ensure 40 char limit
        
        try:
            # Step 1: Create Razorpay order first
            from apps.payments.utils import RazorpayHandler
            handler = RazorpayHandler()
            order_data = handler.create_order(
                amount=course.actual_price,
                currency='INR',
                receipt=receipt,
                notes={
                    'course_id': str(course.id),
                    'course_title': course.title[:100],
                    'user_id': str(request.user.id),
                    'user_email': request.user.email,
                }
            )
            
            if not order_data:
                return Response(
                    {'error': 'Failed to create Razorpay order'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Step 2: Create payment record with razorpay_order_id already set
            payment = Payment.objects.create(
                user=request.user,
                course=course,
                amount=course.actual_price,
                currency='INR',
                status='pending',
                razorpay_order_id=order_data['id']  # Set immediately to avoid unique constraint
            )
            
            return Response({
                'payment_id': str(payment.id),
                'order_id': order_data['id'],
                'amount': float(payment.amount),
                'currency': payment.currency,
                'course_title': course.title,
                 'key_id': settings.RAZORPAY_KEY_ID,
            })
            
        except Exception as e:
            logger.error(f'Failed to create payment order: {str(e)}')
            return Response(
                {'error': f'Failed to create payment order: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def verify_payment(self, request):
        """Verify Razorpay payment"""
        from apps.payments.utils import verify_payment_signature
        
        payment_id = request.data.get('payment_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_signature = request.data.get('razorpay_signature')
        
        if not all([payment_id, razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            return Response(
                {'error': 'All payment details are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if payment is already completed (idempotency)
        if payment.status == 'completed':
            enrollment = Enrollment.objects.filter(
                student=request.user,
                course=payment.course
            ).first()
            if enrollment:
                return Response({
                    'message': 'Payment already verified',
                    'enrollment_id': enrollment.id,
                    'course_id': payment.course.id,
                })
        
        # Step 1: Verify signature
        if not verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            payment.status = 'failed'
            payment.failure_reason = 'Signature verification failed'
            payment.save()
            logger.warning(f'Payment signature verification failed: {payment.id}')
            return Response(
                {'error': 'Payment signature verification failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Step 2: Fetch and validate payment from Razorpay
        from apps.payments.utils import fetch_and_validate_payment
        is_valid, payment_details, error_msg = fetch_and_validate_payment(
            razorpay_payment_id,
            payment.amount,
            razorpay_order_id
        )
        
        if not is_valid:
            payment.status = 'failed'
            payment.failure_reason = error_msg or 'Payment validation failed'
            payment.save()
            logger.error(f'Payment validation failed for {payment.id}: {error_msg}')
            return Response(
                {'error': error_msg or 'Payment validation failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Step 3: Update payment record
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.status = 'completed'
        payment.completed_at = timezone.now()
        payment.save()
        
        # Step 4: Create enrollment (atomic operation)
        enrollment, created = Enrollment.objects.get_or_create(
            student=request.user,
            course=payment.course,
            defaults={'payment_amount': payment.amount}
        )
        
        logger.info(f'Payment verified and enrollment created: payment_id={payment.id}, enrollment_id={enrollment.id}')
        
        return Response({
            'message': 'Payment verified successfully',
            'enrollment_id': enrollment.id,
            'course_id': payment.course.id,
        })
    @action(detail=False, methods=['post'], url_path='validate-coupon')
    def validate_coupon(self, request):
        """Validate a coupon code for a course"""
        from apps.payments.models import Coupon, CouponUsage
        from decimal import Decimal
        
        coupon_code = request.data.get('coupon_code', '').strip()
        course_id = request.data.get('course_id')
        
        if not coupon_code:
            return Response(
                {'valid': False, 'message': 'Please enter a coupon code.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not course_id:
            return Response(
                {'valid': False, 'message': 'Course not specified.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            course = Course.objects.get(id=course_id, status='published')
        except Course.DoesNotExist:
            return Response(
                {'valid': False, 'message': 'Course not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code, status='active')
        except Coupon.DoesNotExist:
            return Response({'valid': False, 'message': 'Invalid coupon code.'})
        
        # Check coupon validity
        is_valid, message = coupon.is_valid()
        if not is_valid:
            return Response({'valid': False, 'message': message})
        
        # Check course applicability
        if coupon.applicable_courses.exists() and course not in coupon.applicable_courses.all():
            return Response({'valid': False, 'message': 'This coupon is not applicable to this course.'})
        
        if coupon.applicable_categories.exists() and course.category not in coupon.applicable_categories.all():
            return Response({'valid': False, 'message': 'This coupon is not applicable to this course category.'})
        
        # Use actual_price if available, otherwise use price
        course_price = getattr(course, 'actual_price', course.price)
        
        if course_price < coupon.min_purchase_amount:
            return Response({
                'valid': False,
                'message': f'Minimum purchase amount of ₹{coupon.min_purchase_amount} required for this coupon.'
            })
        
        # Check user usage limit
        user_usage_count = CouponUsage.objects.filter(coupon=coupon, user=request.user).count()
        if user_usage_count >= coupon.max_uses_per_user:
            return Response({'valid': False, 'message': 'You have already used this coupon the maximum number of times.'})
        
        # Calculate discount
        discount_amount = coupon.calculate_discount(course_price)
        final_amount = course_price - Decimal(str(discount_amount))
        
        return Response({
            'valid': True,
            'message': f'Coupon applied! You save ₹{discount_amount}',
            'discount_amount': float(discount_amount),
            'final_amount': float(final_amount),
            'original_amount': float(course_price),
            'discount_type': coupon.discount_type,
            'discount_value': float(coupon.discount_value)
        })



class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """User subscriptions"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SubscriptionSerializer
    
    def get_queryset(self):
        """Get user's subscriptions"""
        return Subscription.objects.filter(user=self.request.user).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription"""
        subscription = self.get_object()
        
        if subscription.status == 'cancelled':
            return Response(
                {'error': 'Subscription already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        subscription.status = 'cancelled'
        subscription.save()
        
        return Response({
            'message': 'Subscription cancelled successfully',
            'subscription_id': str(subscription.id),
        })


# ============================================================================
# Analytics Views
# ============================================================================

class ListeningSessionViewSet(viewsets.ModelViewSet):
    """Listening session tracking"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ListeningSessionSerializer
    
    def get_queryset(self):
        """Get user's listening sessions"""
        return ListeningSession.objects.filter(
            user=self.request.user
        ).select_related('lesson').order_by('-started_at')
    
    def perform_create(self, serializer):
        """Create session with enrollment"""
        lesson = serializer.validated_data['lesson']
        enrollment = Enrollment.objects.filter(
            student=self.request.user,
            course=lesson.course,
            status='active'
        ).first()
        
        if not enrollment:
            return Response(
                {'error': 'Not enrolled in this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer.save(user=self.request.user, enrollment=enrollment)


class UserStatsView(APIView):
    """User statistics and analytics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user statistics"""
        user = request.user
        
        # Enrollment stats
        total_enrollments = Enrollment.objects.filter(student=user).count()
        active_enrollments = Enrollment.objects.filter(student=user, status='active').count()
        completed_enrollments = Enrollment.objects.filter(student=user, status='completed').count()
        
        # Learning stats
        total_listening_time = Enrollment.objects.filter(
            student=user
        ).aggregate(total=Sum('total_listening_time'))['total'] or 0
        
        total_lessons_completed = LessonProgress.objects.filter(
            enrollment__student=user,
            is_completed=True
        ).count()
        
        # Recent activity
        recent_sessions = ListeningSession.objects.filter(
            user=user
        ).order_by('-started_at')[:10]
        
        return Response({
            'total_enrollments': total_enrollments,
            'active_enrollments': active_enrollments,
            'completed_enrollments': completed_enrollments,
            'total_listening_hours': round(total_listening_time / 3600, 2),
            'total_lessons_completed': total_lessons_completed,
            'recent_activity': ListeningSessionSerializer(
                recent_sessions,
                many=True,
                context={'request': request}
            ).data,
        })


# ============================================================================
# Banner Views
# ============================================================================

class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    """Promotional banners"""
    permission_classes = [permissions.AllowAny]
    serializer_class = MobileBannerSerializer
    
    def get_queryset(self):
        """Get active banners"""
        now = timezone.now()
        return Banner.objects.filter(
            is_active=True,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        ).order_by('-priority', '-start_date')
    
    @action(detail=False, methods=['get'])
    def home(self, request):
        """Get home page banners"""
        banners = self.get_queryset().filter(banner_type='home')

        # Use DRF pagination if enabled so frontend receives {'results': [...]} shape
        page = self.paginate_queryset(banners)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(banners, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path=r'by-type/(?P<banner_type>[^/.]+)')
    def by_type(self, request, banner_type=None):
        """Get banners by type (keeps backward compatibility with older clients)

        Example: /banners/by-type/home/
        """
        if not banner_type:
            return Response({'error': 'banner type is required'}, status=status.HTTP_400_BAD_REQUEST)

        banners = self.get_queryset().filter(banner_type=banner_type)

        # Return paginated response when pagination is configured
        page = self.paginate_queryset(banners)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(banners, many=True, context={'request': request})
        return Response(serializer.data)


# ============================================================================
# Search Views
# ============================================================================

class SearchView(APIView):
    """Unified search endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Search courses"""
        query = request.query_params.get('q', '')
        
        if not query:
            return Response({'results': []})
        
        # Search courses
        courses = Course.objects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query),
            status='published'
        ).select_related('teacher', 'category')[:20]
        
        serializer = CourseSearchSerializer(courses, many=True, context={'request': request})
        
        return Response({
            'query': query,
            'count': len(courses),
            'results': serializer.data,
        })


# ============================================================================
# Dashboard View
# ============================================================================

class DashboardView(APIView):
    """Mobile app dashboard data"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Get dashboard data"""
        # Featured courses
        featured_courses = Course.objects.filter(
            status='published',
            is_featured=True
        ).select_related('teacher', 'category')[:5]
        
        # Trending courses (most enrollments)
        trending_courses = Course.objects.filter(
            status='published'
        ).select_related('teacher', 'category').order_by('-total_enrollments')[:5]
        
        # Categories
        categories = Category.objects.filter(is_active=True)[:10]
        
        # Categories with courses
        categories_with_courses = []
        for category in categories[:5]:  # Limit to 5 categories for performance
            courses = Course.objects.filter(
                status='published',
                category=category
            ).select_related('teacher', 'category')[:10]
            
            if courses.exists():
                categories_with_courses.append({
                    'category': CategorySerializer(category).data,
                    'courses': CourseListSerializer(
                        courses,
                        many=True,
                        context={'request': request}
                    ).data
                })
        
        # Banners
        now = timezone.now()
        banners = Banner.objects.filter(
            is_active=True,
            banner_type='home',
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        ).order_by('-priority')[:3]
        
        data = {
            'featured_courses': CourseListSerializer(
                featured_courses,
                many=True,
                context={'request': request}
            ).data,
            'trending_courses': CourseListSerializer(
                trending_courses,
                many=True,
                context={'request': request}
            ).data,
            'categories': CategorySerializer(categories, many=True).data,
            'categories_with_courses': categories_with_courses,
            'banners': MobileBannerSerializer(
                banners,
                many=True,
                context={'request': request}
            ).data,
        }
        
        # Add user-specific data if authenticated
        if request.user.is_authenticated:
            recent_enrollments = Enrollment.objects.filter(
                student=request.user,
                status='active'
            ).select_related('course').order_by('-last_accessed')[:3]
            
            data['continue_learning'] = EnrollmentSerializer(
                recent_enrollments,
                many=True,
                context={'request': request}
            ).data
        
        return Response(data)


# ============================================================================
# Certificate Views
# ============================================================================

class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """User certificates"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get user's certificates"""
        from apps.courses.models import Certificate
        return Certificate.objects.filter(student=self.request.user).select_related('course')
    
    def get_serializer_class(self):
        from .serializers import CertificateSerializer
        return CertificateSerializer
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download certificate PDF"""
        certificate = self.get_object()
        
        if certificate.certificate_file:
            return Response({
                'url': request.build_absolute_uri(certificate.certificate_file.url),
                'filename': f'certificate_{certificate.certificate_number}.pdf'
            })
        else:
            return Response(
                {'error': 'Certificate file not available'},
                status=status.HTTP_404_NOT_FOUND
            )


# ============================================================================
# User Settings Views
# ============================================================================

class UserSettingsView(APIView):
    """User settings and preferences"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user settings"""
        user = request.user
        
        # Get or create user profile
        if hasattr(user, 'student_profile'):
            profile = user.student_profile
            settings = {
                'notifications_enabled': getattr(profile, 'notifications_enabled', True),
                'email_notifications': getattr(profile, 'email_notifications', True),
                'push_notifications': getattr(profile, 'push_notifications', True),
                'auto_play_next': getattr(profile, 'auto_play_next', True),
                'download_quality': getattr(profile, 'download_quality', 'high'),
                'playback_speed': getattr(profile, 'playback_speed', 1.0),
                'theme': getattr(profile, 'theme', 'light'),
                'language': getattr(profile, 'language', 'en'),
            }
        else:
            settings = {
                'notifications_enabled': True,
                'email_notifications': True,
                'push_notifications': True,
                'auto_play_next': True,
                'download_quality': 'high',
                'playback_speed': 1.0,
                'theme': 'light',
                'language': 'en',
            }
        
        return Response(settings)
    
    def patch(self, request):
        """Update user settings"""
        user = request.user
        
        # Get or create student profile
        from apps.users.models import StudentProfile
        profile, created = StudentProfile.objects.get_or_create(user=user)
        
        # Update settings
        allowed_fields = [
            'notifications_enabled', 'email_notifications', 'push_notifications',
            'auto_play_next', 'download_quality', 'playback_speed', 'theme', 'language'
        ]
        
        for field in allowed_fields:
            if field in request.data:
                setattr(profile, field, request.data[field])
        
        profile.save()
        
        return Response({'message': 'Settings updated successfully'})


# ============================================================================
# Download Management Views
# ============================================================================

class DownloadViewSet(viewsets.ModelViewSet):
    """Manage offline downloads"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get user's downloads"""
        from apps.courses.models import Download
        return Download.objects.filter(user=self.request.user).select_related('lesson')
    
    def get_serializer_class(self):
        from .serializers import DownloadSerializer
        return DownloadSerializer
    
    @action(detail=False, methods=['post'])
    def start_download(self, request):
        """Initiate lesson download"""
        lesson_id = request.data.get('lesson_id')
        
        if not lesson_id:
            return Response(
                {'error': 'Lesson ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': 'Lesson not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check enrollment and download permission
        enrollment = Enrollment.objects.filter(
            student=request.user,
            course=lesson.course,
            status='active'
        ).first()
        
        if not enrollment:
            return Response(
                {'error': 'Not enrolled in this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not lesson.course.allow_download:
            return Response(
                {'error': 'Downloads not allowed for this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create or update download record
        from apps.courses.models import Download
        download, created = Download.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={'status': 'pending'}
        )
        
        if not created and download.status == 'completed':
            return Response({
                'message': 'Already downloaded',
                'download_id': download.id,
                'download_url': request.build_absolute_uri(lesson.audio_file.url) if lesson.audio_file else None
            })
        
        download.status = 'in_progress'
        download.save()
        
        return Response({
            'download_id': download.id,
            'download_url': request.build_absolute_uri(lesson.audio_file.url) if lesson.audio_file else None,
            'lesson_title': lesson.title,
            'file_size': lesson.audio_file.size if lesson.audio_file else 0
        })
    
    @action(detail=True, methods=['delete'])
    def remove_download(self, request, pk=None):
        """Remove downloaded lesson"""
        download = self.get_object()
        download.delete()
        
        return Response({'message': 'Download removed successfully'})
