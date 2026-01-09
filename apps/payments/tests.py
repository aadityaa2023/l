"""
Tests for payment functionality
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.courses.models import Course, Category, Enrollment
from apps.payments.models import Payment
from apps.payments.utils import RazorpayHandler
from unittest.mock import patch, MagicMock
import json

User = get_user_model()


class PaymentViewTests(TestCase):
    """Test payment views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create users
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.teacher = User.objects.create_user(
            username='teacher',
            email='teacher@test.com',
            password='testpass123',
            user_type='teacher'
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        # Create course
        self.course = Course.objects.create(
            title='Test Course',
            slug='test-course',
            teacher=self.teacher,
            category=self.category,
            price=999,
            status='published'
        )
    
    @patch('apps.payments.utils.RazorpayHandler.create_order')
    def test_course_payment_view(self, mock_create_order):
        """Test course payment view creates order"""
        # Mock Razorpay order creation
        mock_create_order.return_value = {
            'id': 'order_test123',
            'amount': 99900,
            'currency': 'INR'
        }
        
        self.client.login(username='student', password='testpass123')
        response = self.client.get(
            reverse('payments:course_payment', kwargs={'course_id': self.course.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/course_payment.html')
        self.assertIn('order', response.context)
        self.assertIn('course', response.context)
        
        # Check payment record created
        payment = Payment.objects.filter(user=self.student, course=self.course).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, 'pending')
    
    @patch('apps.payments.utils.RazorpayHandler.verify_payment_signature')
    def test_verify_payment_success(self, mock_verify):
        """Test successful payment verification"""
        # Create pending payment
        payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=999,
            currency='INR',
            razorpay_order_id='order_test123',
            status='pending'
        )
        
        # Mock signature verification
        mock_verify.return_value = True
        
        self.client.login(username='student', password='testpass123')
        response = self.client.post(
            reverse('payments:verify_payment'),
            data=json.dumps({
                'razorpay_order_id': 'order_test123',
                'razorpay_payment_id': 'pay_test123',
                'razorpay_signature': 'signature_test'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Check payment updated
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(payment.razorpay_payment_id, 'pay_test123')
        
        # Check enrollment created
        enrollment = Enrollment.objects.filter(
            student=self.student,
            course=self.course
        ).first()
        self.assertIsNotNone(enrollment)


class RazorpayHandlerTests(TestCase):
    """Test Razorpay utility functions"""
    
    def test_convert_to_paise(self):
        """Test conversion from rupees to paise"""
        from apps.payments.utils import convert_to_paise
        
        self.assertEqual(convert_to_paise(100), 10000)
        self.assertEqual(convert_to_paise(999.50), 99950)
        self.assertEqual(convert_to_paise(1), 100)
    
    def test_convert_from_paise(self):
        """Test conversion from paise to rupees"""
        from apps.payments.utils import convert_from_paise
        
        self.assertEqual(convert_from_paise(10000), 100.00)
        self.assertEqual(convert_from_paise(99950), 999.50)
        self.assertEqual(convert_from_paise(100), 1.00)


class PaymentModelTests(TestCase):
    """Test payment models"""
    
    def setUp(self):
        """Set up test data"""
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.teacher = User.objects.create_user(
            username='teacher',
            email='teacher@test.com',
            password='testpass123',
            user_type='teacher'
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        
        self.course = Course.objects.create(
            title='Test Course',
            slug='test-course',
            teacher=self.teacher,
            category=self.category,
            price=999,
            status='published'
        )
    
    def test_payment_creation(self):
        """Test creating a payment record"""
        payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=999,
            currency='INR',
            razorpay_order_id='order_test123',
            status='pending'
        )
        
        self.assertEqual(payment.user, self.student)
        self.assertEqual(payment.course, self.course)
        self.assertEqual(payment.amount, 999)
        self.assertEqual(payment.status, 'pending')
        self.assertIsNotNone(payment.created_at)

