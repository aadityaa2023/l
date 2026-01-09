"""
REST API endpoints for platformadmin automation
Allows programmatic access to admin functions
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from decimal import Decimal

from apps.platformadmin.permissions import PermissionChecker, AdminPermissions
from apps.platformadmin.models import AdminLog, CourseApproval, PlatformSetting
from apps.platformadmin.payment_handlers import RefundHandler, BulkPaymentHandler
from apps.platformadmin.utils import DashboardStats, ReportGenerator
from apps.courses.models import Course
from apps.payments.models import Payment, Refund

User = get_user_model()


class IsAdminUser(IsAuthenticated):
    """Permission class for admin-only API access"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role == 'admin' and request.user.is_staff


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 
                  'is_active', 'email_verified', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Payment
        fields = ['id', 'user_email', 'course_title', 'amount', 'currency',
                  'status', 'payment_method', 'created_at', 'completed_at']
        read_only_fields = ['id', 'created_at']


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for Refund model"""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    payment_id = serializers.UUIDField(source='payment.id', read_only=True)
    
    class Meta:
        model = Refund
        fields = ['id', 'payment_id', 'user_email', 'amount', 'status',
                  'reason', 'requested_at', 'processed_at']
        read_only_fields = ['id', 'requested_at', 'processed_at']


class AdminLogSerializer(serializers.ModelSerializer):
    """Serializer for AdminLog model"""
    
    admin_email = serializers.EmailField(source='admin.email', read_only=True)
    
    class Meta:
        model = AdminLog
        fields = ['id', 'admin_email', 'action', 'content_type', 'object_id',
                  'object_repr', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']


@api_view(['GET'])
@permission_classes([IsAdminUser])
def dashboard_stats_api(request):
    """
    Get dashboard statistics
    GET /api/admin/stats/
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.VIEW_DASHBOARD):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    stats = DashboardStats.get_all_stats()
    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def revenue_report_api(request):
    """
    Get revenue report
    GET /api/admin/reports/revenue/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.VIEW_FINANCIAL_REPORTS):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    from datetime import datetime
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    report = ReportGenerator.get_revenue_report(start_date, end_date)
    
    # Convert Decimal to string for JSON serialization
    report['total_revenue'] = str(report['total_revenue'])
    report['avg_daily_revenue'] = str(report['avg_daily_revenue'])
    
    return Response(report)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def process_refund_api(request, payment_id):
    """
    Process a refund
    POST /api/admin/refunds/{payment_id}/
    Body: {
        "amount": 99.99,  // optional, full refund if not provided
        "reason": "not_satisfied",
        "admin_notes": "Customer requested refund"
    }
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.PROCESS_REFUNDS):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    amount = request.data.get('amount')
    reason = request.data.get('reason', 'other')
    admin_notes = request.data.get('admin_notes', '')
    
    if amount:
        try:
            amount = Decimal(str(amount))
        except:
            return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)
    
    handler = RefundHandler()
    success, message, refund_obj = handler.process_refund(
        payment=payment,
        admin_user=request.user,
        amount=amount,
        reason=reason,
        admin_notes=admin_notes
    )
    
    if success:
        return Response({
            'success': True,
            'message': message,
            'refund': RefundSerializer(refund_obj).data
        })
    else:
        return Response({
            'success': False,
            'message': message
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_refund_api(request):
    """
    Process bulk refunds
    POST /api/admin/refunds/bulk/
    Body: {
        "payment_ids": ["uuid1", "uuid2", ...],
        "reason": "admin_discretion",
        "admin_notes": "Bulk refund for promotion"
    }
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.PROCESS_REFUNDS):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    payment_ids = request.data.get('payment_ids', [])
    reason = request.data.get('reason', 'other')
    admin_notes = request.data.get('admin_notes', '')
    
    if not payment_ids:
        return Response({'error': 'No payment IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    handler = BulkPaymentHandler()
    results = handler.bulk_refund(
        payment_ids=payment_ids,
        admin_user=request.user,
        reason=reason,
        admin_notes=admin_notes
    )
    
    return Response(results)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def activate_user_api(request, user_id):
    """
    Activate a user
    POST /api/admin/users/{user_id}/activate/
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.MANAGE_USERS):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    user.is_active = True
    user.save()
    
    from apps.platformadmin.utils import ActivityLog
    ActivityLog.log_user_action(
        user, request.user, 'activate',
        {'is_active': False}, {'is_active': True},
        request.data.get('reason', '')
    )
    
    return Response({
        'success': True,
        'message': f'User {user.email} activated',
        'user': UserSerializer(user).data
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def deactivate_user_api(request, user_id):
    """
    Deactivate a user
    POST /api/admin/users/{user_id}/deactivate/
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.MANAGE_USERS):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    user.is_active = False
    user.save()
    
    from apps.platformadmin.utils import ActivityLog
    ActivityLog.log_user_action(
        user, request.user, 'deactivate',
        {'is_active': True}, {'is_active': False},
        request.data.get('reason', '')
    )
    
    return Response({
        'success': True,
        'message': f'User {user.email} deactivated',
        'user': UserSerializer(user).data
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def user_list_api(request):
    """
    Get list of users
    GET /api/admin/users/?role=student&status=active&search=email
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.VIEW_USERS):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    users = User.objects.exclude(role='admin')
    
    # Filters
    role = request.GET.get('role')
    if role in ['student', 'teacher']:
        users = users.filter(role=role)
    
    status_filter = request.GET.get('status')
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 20
    result_page = paginator.paginate_queryset(users, request)
    
    serializer = UserSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def payment_list_api(request):
    """
    Get list of payments
    GET /api/admin/payments/?status=completed&date_from=YYYY-MM-DD
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.VIEW_PAYMENTS):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    payments = Payment.objects.select_related('user', 'course')
    
    # Filters
    status_filter = request.GET.get('status')
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    date_from = request.GET.get('date_from')
    if date_from:
        from datetime import datetime
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        payments = payments.filter(created_at__date__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        from datetime import datetime
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        payments = payments.filter(created_at__date__lte=date_to)
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 20
    result_page = paginator.paginate_queryset(payments, request)
    
    serializer = PaymentSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_logs_api(request):
    """
    Get admin activity logs
    GET /api/admin/logs/?action=refund&admin=admin@test.com
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.VIEW_LOGS):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    logs = AdminLog.objects.select_related('admin')
    
    # Filters
    action = request.GET.get('action')
    if action:
        logs = logs.filter(action=action)
    
    admin_email = request.GET.get('admin')
    if admin_email:
        logs = logs.filter(admin__email=admin_email)
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 50
    result_page = paginator.paginate_queryset(logs, request)
    
    serializer = AdminLogSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def approve_course_api(request, course_id):
    """
    Approve a course
    POST /api/admin/courses/{course_id}/approve/
    Body: {
        "comments": "Great course!"
    }
    """
    if not PermissionChecker.has_permission(request.user, AdminPermissions.APPROVE_COURSES):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
    
    approval, created = CourseApproval.objects.get_or_create(course=course)
    approval.status = 'approved'
    approval.reviewed_by = request.user
    approval.reviewed_at = timezone.now()
    approval.review_comments = request.data.get('comments', '')
    approval.save()
    
    from apps.platformadmin.utils import ActivityLog
    from django.utils import timezone
    ActivityLog.log_course_action(
        course, request.user, 'approve',
        {'status': 'pending'}, {'status': 'approved'},
        request.data.get('comments', '')
    )
    
    return Response({
        'success': True,
        'message': f'Course "{course.title}" approved'
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_health_api(request):
    """
    Get system health metrics
    GET /api/admin/system/health/
    """
    from apps.platformadmin.payment_handlers import PaymentAnalytics
    
    disputes = PaymentAnalytics.get_payment_disputes()
    
    health_status = 'healthy'
    if disputes['old_pending_payments'] > 10 or disputes['recent_failed_payments'] > 20:
        health_status = 'warning'
    if disputes['recent_failed_payments'] > 50:
        health_status = 'critical'
    
    return Response({
        'status': health_status,
        'metrics': disputes,
        'timestamp': timezone.now()
    })
