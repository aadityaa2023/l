"""
URL configuration for payments app
"""
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Course Payment
    path('course/<int:course_id>/', views.course_payment, name='course_payment'),
    path('verify/', views.verify_payment, name='verify_payment'),
    
    # Payment Status
    path('success/', views.payment_success, name='payment_success'),
    path('failed/', views.payment_failed, name='payment_failed'),
    
    # Payment History
    path('my-payments/', views.my_payments, name='my_payments'),
    
    # Refunds
    path('refund/<int:payment_id>/', views.request_refund, name='request_refund'),
    
    # Webhooks
    path('webhook/', views.razorpay_webhook, name='razorpay_webhook'),
]
