"""
API URLs for platformadmin
"""
from django.urls import path
from apps.platformadmin import api_views

app_name = 'platformadmin_api'

urlpatterns = [
    # Dashboard & Stats
    path('stats/', api_views.dashboard_stats_api, name='dashboard_stats'),
    path('reports/revenue/', api_views.revenue_report_api, name='revenue_report'),
    path('system/health/', api_views.system_health_api, name='system_health'),
    
    # Users
    path('users/', api_views.user_list_api, name='user_list'),
    path('users/<int:user_id>/activate/', api_views.activate_user_api, name='activate_user'),
    path('users/<int:user_id>/deactivate/', api_views.deactivate_user_api, name='deactivate_user'),
    
    # Payments
    path('payments/', api_views.payment_list_api, name='payment_list'),
    
    # Refunds
    path('refunds/<uuid:payment_id>/', api_views.process_refund_api, name='process_refund'),
    path('refunds/bulk/', api_views.bulk_refund_api, name='bulk_refund'),
    
    # Courses
    path('courses/<int:course_id>/approve/', api_views.approve_course_api, name='approve_course'),
    
    # Logs
    path('logs/', api_views.admin_logs_api, name='admin_logs'),
]
