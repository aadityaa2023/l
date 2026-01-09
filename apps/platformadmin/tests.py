"""
Unit tests for Platform Admin
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from apps.platformadmin.models import AdminLog, CourseApproval, DashboardStat, PlatformSetting
from apps.platformadmin.utils import DashboardStats, ReportGenerator, ActivityLog
from apps.courses.models import Course, Category
from apps.payments.models import Payment

User = get_user_model()


class PlatformAdminAccessTestCase(TestCase):
    """Test access control for platform admin"""
    
    def setUp(self):
        """Set up test users"""
        # Create platform admin
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role='admin',
            is_staff=True,
            is_active=True
        )
        
        # Create regular student
        self.student_user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student',
            is_active=True
        )
        
        # Create teacher
        self.teacher_user = User.objects.create_user(
            email='teacher@test.com',
            password='testpass123',
            role='teacher',
            is_active=True
        )
        
        self.client = Client()
    
    def test_admin_can_access_dashboard(self):
        """Platform admin should access dashboard"""
        self.client.login(email='admin@test.com', password='testpass123')
        response = self.client.get(reverse('platformadmin:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin Dashboard')
    
    def test_student_cannot_access_dashboard(self):
        """Students should not access platform admin"""
        self.client.login(email='student@test.com', password='testpass123')
        response = self.client.get(reverse('platformadmin:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_teacher_cannot_access_dashboard(self):
        """Teachers should not access platform admin"""
        self.client.login(email='teacher@test.com', password='testpass123')
        response = self.client.get(reverse('platformadmin:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_anonymous_cannot_access_dashboard(self):
        """Anonymous users should not access platform admin"""
        response = self.client.get(reverse('platformadmin:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login


class DashboardStatsTestCase(TestCase):
    """Test dashboard statistics utility"""
    
    def setUp(self):
        """Create test data"""
        # Create users
        self.teacher = User.objects.create_user(
            email='teacher@test.com',
            password='test123',
            role='teacher',
            is_active=True
        )
        
        self.student = User.objects.create_user(
            email='student@test.com',
            password='test123',
            role='student',
            is_active=True
        )
        
        # Create category
        self.category = Category.objects.create(name='Test Category')
        
        # Create course
        self.course = Course.objects.create(
            title='Test Course',
            description='Test description',
            teacher=self.teacher,
            category=self.category,
            price=Decimal('100.00'),
            status='published'
        )
    
    def test_get_user_stats(self):
        """Test user statistics generation"""
        stats = DashboardStats.get_user_stats()
        
        self.assertIn('total_users', stats)
        self.assertIn('total_teachers', stats)
        self.assertIn('total_students', stats)
        self.assertEqual(stats['total_teachers'], 1)
        self.assertEqual(stats['total_students'], 1)
    
    def test_get_course_stats(self):
        """Test course statistics generation"""
        stats = DashboardStats.get_course_stats()
        
        self.assertIn('total_courses', stats)
        self.assertIn('published_courses', stats)
        self.assertEqual(stats['total_courses'], 1)
        self.assertEqual(stats['published_courses'], 1)
    
    def test_get_all_stats(self):
        """Test getting all statistics"""
        stats = DashboardStats.get_all_stats()
        
        self.assertIn('users', stats)
        self.assertIn('courses', stats)
        self.assertIn('revenue', stats)
        self.assertIn('enrollments', stats)


class ActivityLogTestCase(TestCase):
    """Test activity logging"""
    
    def setUp(self):
        """Create admin user"""
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='test123',
            role='admin',
            is_staff=True
        )
        
        self.student = User.objects.create_user(
            email='student@test.com',
            password='test123',
            role='student'
        )
    
    def test_log_user_action(self):
        """Test logging user management action"""
        old_values = {'is_active': True}
        new_values = {'is_active': False}
        
        ActivityLog.log_user_action(
            self.student, 
            self.admin, 
            'deactivate',
            old_values,
            new_values,
            'Test deactivation'
        )
        
        log = AdminLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.admin, self.admin)
        self.assertEqual(log.action, 'deactivate')
        self.assertEqual(log.content_type, 'User')
        self.assertEqual(log.object_repr, self.student.email)
    
    def test_get_recent_logs(self):
        """Test retrieving recent logs"""
        # Create multiple logs
        for i in range(5):
            AdminLog.objects.create(
                admin=self.admin,
                action='update',
                content_type='User',
                object_id=str(i),
                object_repr=f'User {i}'
            )
        
        logs = ActivityLog.get_recent_logs(3)
        self.assertEqual(len(logs), 3)


class CourseApprovalTestCase(TestCase):
    """Test course approval functionality"""
    
    def setUp(self):
        """Create test data"""
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='test123',
            role='admin',
            is_staff=True
        )
        
        self.teacher = User.objects.create_user(
            email='teacher@test.com',
            password='test123',
            role='teacher'
        )
        
        self.category = Category.objects.create(name='Test Category')
        
        self.course = Course.objects.create(
            title='Test Course',
            description='Test description',
            teacher=self.teacher,
            category=self.category,
            status='draft'
        )
        
        self.client = Client()
    
    def test_create_course_approval(self):
        """Test creating course approval"""
        approval = CourseApproval.objects.create(
            course=self.course,
            status='pending'
        )
        
        self.assertEqual(approval.status, 'pending')
        self.assertIsNone(approval.reviewed_by)
    
    def test_approve_course(self):
        """Test approving a course"""
        approval = CourseApproval.objects.create(
            course=self.course,
            status='pending'
        )
        
        self.client.login(email='admin@test.com', password='test123')
        
        response = self.client.post(
            reverse('platformadmin:course_approval', args=[self.course.id]),
            {
                'status': 'approved',
                'review_comments': 'Looks good!'
            }
        )
        
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'approved')
        self.assertEqual(approval.reviewed_by, self.admin)
        self.assertIsNotNone(approval.reviewed_at)


class PlatformSettingTestCase(TestCase):
    """Test platform settings"""
    
    def test_create_setting(self):
        """Test creating platform setting"""
        setting = PlatformSetting.objects.create(
            key='commission_percentage',
            value='10.00',
            setting_type='decimal',
            description='Platform commission percentage'
        )
        
        self.assertEqual(setting.key, 'commission_percentage')
        self.assertEqual(setting.value, '10.00')
    
    def test_update_setting(self):
        """Test updating platform setting"""
        setting = PlatformSetting.objects.create(
            key='max_course_price',
            value='10000',
            setting_type='integer'
        )
        
        setting.value = '15000'
        setting.save()
        
        setting.refresh_from_db()
        self.assertEqual(setting.value, '15000')


class ReportGeneratorTestCase(TestCase):
    """Test report generation"""
    
    def setUp(self):
        """Create test data"""
        self.student = User.objects.create_user(
            email='student@test.com',
            password='test123',
            role='student'
        )
        
        self.teacher = User.objects.create_user(
            email='teacher@test.com',
            password='test123',
            role='teacher'
        )
        
        self.category = Category.objects.create(name='Test Category')
        
        self.course = Course.objects.create(
            title='Test Course',
            description='Test',
            teacher=self.teacher,
            category=self.category,
            price=Decimal('100.00')
        )
    
    def test_revenue_report(self):
        """Test revenue report generation"""
        # Create payment
        payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal('100.00'),
            status='completed',
            completed_at=timezone.now()
        )
        
        report = ReportGenerator.get_revenue_report()
        
        self.assertIn('total_revenue', report)
        self.assertIn('daily_revenue', report)
        self.assertGreater(report['total_revenue'], 0)
    
    def test_user_report(self):
        """Test user growth report"""
        report = ReportGenerator.get_user_report()
        
        self.assertIn('total_new_users', report)
        self.assertIn('new_teachers', report)
        self.assertIn('new_students', report)
        self.assertIn('daily_users', report)
    
    def test_course_stats_report(self):
        """Test course statistics report"""
        report = ReportGenerator.get_course_stats_report()
        
        self.assertIn('total_courses', report)
        self.assertIn('by_status', report)
        self.assertIn('by_teacher', report)


class UserManagementTestCase(TestCase):
    """Test user management views"""
    
    def setUp(self):
        """Set up test data"""
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='test123',
            role='admin',
            is_staff=True
        )
        
        self.student = User.objects.create_user(
            email='student@test.com',
            password='test123',
            role='student'
        )
        
        self.client = Client()
        self.client.login(email='admin@test.com', password='test123')
    
    def test_user_list_view(self):
        """Test user management list view"""
        response = self.client.get(reverse('platformadmin:user_management'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User Management')
        self.assertContains(response, self.student.email)
    
    def test_user_detail_view(self):
        """Test user detail view"""
        response = self.client.get(
            reverse('platformadmin:user_detail', args=[self.student.id])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.email)
    
    def test_user_filter_by_role(self):
        """Test filtering users by role"""
        response = self.client.get(
            reverse('platformadmin:user_management') + '?role=student'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.email)
    
    def test_user_search(self):
        """Test user search"""
        response = self.client.get(
            reverse('platformadmin:user_management') + '?search=student'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.email)
