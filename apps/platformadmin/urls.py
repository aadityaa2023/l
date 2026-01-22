"""
URL Configuration for Platform Admin
"""
from django.urls import path
from apps.platformadmin import views, advanced_views, comprehensive_views

app_name = 'platformadmin'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # User Management
    path('users/', views.user_management, name='user_management'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('teachers/', views.teacher_verification, name='teacher_verification'),
    
    # Bulk User Actions
    path('users/bulk-action/', advanced_views.bulk_user_action, name='bulk_user_action'),
    
    # Course Management
    path('courses/', views.course_management, name='course_management'),
    path('courses/<int:course_id>/approve/', views.course_approval, name='course_approval'),
    
    # Platform Admin Course CRUD & Assignment
    path('admin-courses/', views.admin_courses_list, name='admin_courses_list'),
    path('admin-courses/create/', views.admin_course_create, name='admin_course_create'),
    path('admin-courses/<int:course_id>/edit/', views.admin_course_edit, name='admin_course_edit'),
    path('admin-courses/<int:course_id>/delete/', views.admin_course_delete, name='admin_course_delete'),
    path('admin-courses/<int:course_id>/assign/', views.admin_course_assign, name='admin_course_assign'),
    path('admin-courses/assignment/<uuid:assignment_id>/unassign/', views.admin_course_unassign, name='admin_course_unassign'),
    path('admin-courses/assignments/', views.admin_view_all_assignments, name='admin_view_all_assignments'),
    
    # Platform Admin Module Management
    path('admin-courses/<int:course_id>/module/create/', views.admin_module_create, name='admin_module_create'),
    path('admin-courses/module/<int:module_id>/edit/', views.admin_module_edit, name='admin_module_edit'),
    path('admin-courses/module/<int:module_id>/delete/', views.admin_module_delete, name='admin_module_delete'),
    path('admin-courses/<int:course_id>/modules/reorder/', views.admin_module_reorder, name='admin_module_reorder'),
    
    # Platform Admin Lesson Management
    path('admin-courses/module/<int:module_id>/lesson/create/', views.admin_lesson_create, name='admin_lesson_create'),
    path('admin-courses/lesson/<int:lesson_id>/edit/', views.admin_lesson_edit, name='admin_lesson_edit'),
    path('admin-courses/lesson/<int:lesson_id>/delete/', views.admin_lesson_delete, name='admin_lesson_delete'),
    path('admin-courses/module/<int:module_id>/lessons/reorder/', views.admin_lesson_reorder, name='admin_lesson_reorder'),
    path('admin-courses/lesson-media/<int:media_id>/delete/', views.admin_lesson_media_delete, name='admin_lesson_media_delete'),
    
    # Category Management
    path('categories/', views.admin_category_management, name='admin_category_management'),
    path('categories/create/', views.admin_category_create, name='admin_category_create'),
    path('categories/<int:category_id>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('categories/<int:category_id>/delete/', views.admin_category_delete, name='admin_category_delete'),
    
    # Payment Management
    path('payments/', views.payment_management, name='payment_management'),
    path('payments/<uuid:payment_id>/', views.payment_detail, name='payment_detail'),
    path('payments/bulk-refund/', advanced_views.bulk_refund_action, name='bulk_refund_action'),
    
    # Coupon & Promo Code Management
    path('coupons/', comprehensive_views.coupon_management, name='coupon_management'),
    path('coupons/create/', comprehensive_views.coupon_create, name='coupon_create'),
    path('coupons/<int:coupon_id>/edit/', comprehensive_views.coupon_edit, name='coupon_edit'),
    path('coupons/<int:coupon_id>/delete/', comprehensive_views.coupon_delete, name='coupon_delete'),
    path('coupons/statistics/', comprehensive_views.coupon_statistics, name='coupon_statistics'),
    
    # Review & Rating Moderation
    path('reviews/', comprehensive_views.review_moderation, name='review_moderation'),
    path('reviews/<int:review_id>/approve/', comprehensive_views.review_approve, name='review_approve'),
    path('reviews/<int:review_id>/delete/', comprehensive_views.review_delete, name='review_delete'),
    
    # Subscription Management
    path('subscriptions/', comprehensive_views.subscription_management, name='subscription_management'),
    path('subscriptions/<uuid:subscription_id>/cancel/', comprehensive_views.subscription_cancel, name='subscription_cancel'),
    
    # Instructor Earnings & Payouts
    path('earnings/', comprehensive_views.instructor_earnings, name='instructor_earnings'),
    path('payouts/', comprehensive_views.payout_management, name='payout_management'),
    path('payouts/process/', comprehensive_views.payout_process, name='payout_process'),
    path('payouts/history/<int:teacher_id>/', comprehensive_views.payout_history, name='payout_history'),
    
    # Login History & Security
    path('security/login-history/', comprehensive_views.login_history, name='login_history'),
    path('security/student-progress/', comprehensive_views.student_progress, name='student_progress'),
    
    # CMS Management
    path('cms/', comprehensive_views.cms_management, name='cms_management'),
    path('cms/create/', comprehensive_views.cms_page_create, name='cms_page_create'),
    path('cms/<int:page_id>/edit/', comprehensive_views.cms_page_edit, name='cms_page_edit'),
    path('cms/<int:page_id>/delete/', comprehensive_views.cms_page_delete, name='cms_page_delete'),
    path('cms/faq/', comprehensive_views.faq_management, name='faq_management'),
    path('cms/faq/create/', comprehensive_views.faq_create, name='faq_create'),
    path('cms/faq/<int:faq_id>/edit/', comprehensive_views.faq_edit, name='faq_edit'),
    path('cms/faq/<int:faq_id>/delete/', comprehensive_views.faq_delete, name='faq_delete'),
    path('cms/announcements/', comprehensive_views.announcement_management, name='announcement_management'),
    path('cms/announcements/create/', comprehensive_views.announcement_create, name='announcement_create'),
    path('cms/announcements/<int:announcement_id>/edit/', comprehensive_views.announcement_edit, name='announcement_edit'),
    path('cms/announcements/<int:announcement_id>/delete/', comprehensive_views.announcement_delete, name='announcement_delete'),
    
    # Marketing (referral feature removed)
    
    # Video/Content Control
    path('settings/video/', comprehensive_views.video_settings, name='video_settings'),
    
    # Push Notifications
    path('notifications/', comprehensive_views.notification_management, name='notification_management'),
    path('notifications/send-bulk/', comprehensive_views.send_bulk_notification, name='send_bulk_notification'),
    
    # Analytics & Reports
    path('analytics/', views.analytics_report, name='analytics_report'),
    path('analytics/advanced/', advanced_views.advanced_analytics, name='advanced_analytics'),
    path('analytics/teachers/', advanced_views.teacher_analytics, name='teacher_analytics'),
    path('logs/', views.activity_logs, name='activity_logs'),
    
    # CSV Exports
    path('export/users/', advanced_views.export_users_csv, name='export_users_csv'),
    path('export/courses/', advanced_views.export_courses_csv, name='export_courses_csv'),
    path('export/payments/', advanced_views.export_payments_csv, name='export_payments_csv'),
    path('export/refunds/', advanced_views.export_refunds_csv, name='export_refunds_csv'),
    path('export/logs/', advanced_views.export_admin_logs_csv, name='export_admin_logs_csv'),
    
    # System Management
    path('settings/', views.platform_settings, name='platform_settings'),
    path('system/health/', advanced_views.system_health, name='system_health'),
    path('system/clear-cache/', advanced_views.clear_cache, name='clear_cache'),
    
    # Email Template Previews
    path('emails/', views.email_templates_list, name='email_templates_list'),
    path('emails/preview/<str:template_name>/', views.email_preview, name='email_preview'),
    
    # Banner Management
    path('banners/', views.banner_list, name='banner_list'),
    path('banners/create/', views.banner_create, name='banner_create'),
    path('banners/<int:banner_id>/edit/', views.banner_edit, name='banner_edit'),
    path('banners/<int:banner_id>/delete/', views.banner_delete, name='banner_delete'),
    path('banners/<int:banner_id>/toggle-status/', views.banner_toggle_status, name='banner_toggle_status'),
]

