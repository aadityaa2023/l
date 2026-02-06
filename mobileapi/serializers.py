"""
Serializers for Mobile API
Optimized for mobile app consumption with nested data and minimal requests
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.courses.models import Course, Category, Module, Lesson, Enrollment, LessonProgress, Review
from apps.common.models import Banner
from apps.notifications.models import Notification
from apps.payments.models import Payment, Subscription
from apps.analytics.models import ListeningSession


User = get_user_model()


# ============================================================================
# User & Authentication Serializers
# ============================================================================

class UserProfileSerializer(serializers.ModelSerializer):
    """User profile information for mobile app"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField(read_only=True)
    total_enrollments = serializers.SerializerMethodField()
    total_completed = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'phone',
            'role',
            'profile_picture_url',
            'profile_picture',
            'email_verified',
            'date_joined',
            'total_enrollments',
            'total_completed',
        ]
        read_only_fields = ['id', 'email', 'role', 'date_joined']
    
    def get_profile_picture_url(self, obj):
        """Get profile picture URL if available"""
        if hasattr(obj, 'student_profile') and obj.student_profile.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.student_profile.profile_picture.url)
            return obj.student_profile.profile_picture.url
        return None
    
    def get_profile_picture(self, obj):
        """Alias for profile_picture_url for compatibility"""
        return self.get_profile_picture_url(obj)
    
    def get_total_enrollments(self, obj):
        """Count active enrollments"""
        return obj.enrollments.filter(status='active').count()
    
    def get_total_completed(self, obj):
        """Count completed enrollments"""
        return obj.enrollments.filter(status='completed').count()
    
    def update(self, instance, validated_data):
        """Update user and handle profile picture upload"""
        # Handle file upload
        if 'profile_picture' in self.context.get('request').FILES:
            profile_picture = self.context.get('request').FILES['profile_picture']
            
            # Get or create student profile
            from apps.users.models import StudentProfile
            student_profile, _ = StudentProfile.objects.get_or_create(user=instance)
            student_profile.profile_picture = profile_picture
            student_profile.save()
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    phone = serializers.CharField(required=True, allow_blank=False)
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'password', 'password_confirm']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            role='student'
        )
        return user


# ============================================================================
# Course Serializers
# ============================================================================

class CategorySerializer(serializers.ModelSerializer):
    """Category serializer for mobile"""
    course_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'icon', 'course_count']
    
    def get_course_count(self, obj):
        """Count published courses in category"""
        return obj.courses.filter(status='published').count()


class LessonListSerializer(serializers.ModelSerializer):
    """Lightweight lesson serializer for listing"""
    audio_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    duration_minutes = serializers.FloatField(read_only=True)
    is_completed = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = [
            'id',
            'title',
            'description',
            'lesson_type',
            'order',
            'audio_url',
            'video_url',
            'duration_seconds',
            'duration_minutes',
            'is_free_preview',
            'is_completed',
            'progress_percentage',
        ]
    
    def get_audio_url(self, obj):
        """Get audio file URL"""
        # Primary: Lesson.audio_file for audio lessons
        if obj.lesson_type == 'audio' and obj.audio_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.audio_file.url)
            return obj.audio_file.url

        # Fallback: check related LessonMedia entries (media_type='audio')
        media_qs = getattr(obj, 'media_files', None)
        if media_qs is not None:
            audio_media = media_qs.filter(media_type='audio').order_by('order').first()
            if audio_media and audio_media.media_file:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(audio_media.media_file.url)
                return audio_media.media_file.url

        return None
    
    def get_video_url(self, obj):
        """Get video file URL (uses audio_file field for video lessons)"""
        # Primary: Lesson.audio_file may hold video for video lessons
        if obj.lesson_type == 'video' and obj.audio_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.audio_file.url)
            return obj.audio_file.url

        # Fallback: check related LessonMedia entries (media_type='video')
        media_qs = getattr(obj, 'media_files', None)
        if media_qs is not None:
            video_media = media_qs.filter(media_type='video').order_by('order').first()
            if video_media and video_media.media_file:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(video_media.media_file.url)
                return video_media.media_file.url

        return None
    
    def get_is_completed(self, obj):
        """Check if lesson is completed by current user"""
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            enrollment = self.context.get('enrollment')
            if enrollment:
                progress = LessonProgress.objects.filter(
                    enrollment=enrollment,
                    lesson=obj
                ).first()
                return progress.is_completed if progress else False
        return False
    
    def get_progress_percentage(self, obj):
        """Get lesson progress percentage"""
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            enrollment = self.context.get('enrollment')
            if enrollment:
                progress = LessonProgress.objects.filter(
                    enrollment=enrollment,
                    lesson=obj
                ).first()
                return float(progress.completion_percentage) if progress else 0
        return 0


class LessonDetailSerializer(LessonListSerializer):
    """Detailed lesson serializer with full content"""
    module_title = serializers.CharField(source='module.title', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    last_position_seconds = serializers.SerializerMethodField()
    
    class Meta(LessonListSerializer.Meta):
        fields = LessonListSerializer.Meta.fields + [
            'text_content',
            'module_title',
            'course_title',
            'last_position_seconds',
            'created_at',
        ]
    
    def get_last_position_seconds(self, obj):
        """Get last playback position for user"""
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            enrollment = self.context.get('enrollment')
            if enrollment:
                progress = LessonProgress.objects.filter(
                    enrollment=enrollment,
                    lesson=obj
                ).first()
                return progress.last_position_seconds if progress else 0
        return 0


class ModuleSerializer(serializers.ModelSerializer):
    """Module serializer with lessons"""
    lessons = LessonListSerializer(many=True, read_only=True)
    lesson_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Module
        fields = [
            'id',
            'title',
            'description',
            'order',
            'lesson_count',
            'lessons',
        ]
    
    def get_lesson_count(self, obj):
        """Count published lessons"""
        return obj.lessons.filter(is_published=True).count()


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight course serializer for listing"""
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    actual_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'short_description',
            'teacher_name',
            'category_name',
            'thumbnail_url',
            'level',
            'language',
            'duration_hours',
            'price',
            'discount_price',
            'actual_price',
            'is_free',
            'is_featured',
            'average_rating',
            'total_reviews',
            'total_enrollments',
            'is_enrolled',
        ]
    
    def get_thumbnail_url(self, obj):
        """Get thumbnail URL"""
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None
    
    def get_is_enrolled(self, obj):
        """Check if current user is enrolled"""
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return obj.enrollments.filter(student=user, status__in=['active', 'completed']).exists()
        return False


class CourseDetailSerializer(CourseListSerializer):
    """Detailed course serializer with modules and lessons"""
    modules = ModuleSerializer(many=True, read_only=True)
    enrollment = serializers.SerializerMethodField()
    
    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + [
            'description',
            'intro_video_url',
            'total_lessons',
            'allow_download',
            'modules',
            'enrollment',
            'created_at',
            'published_at',
        ]
    
    def get_enrollment(self, obj):
        """Get user's enrollment details if enrolled"""
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            enrollment = obj.enrollments.filter(student=user, status__in=['active', 'completed']).first()
            if enrollment:
                return EnrollmentSerializer(enrollment, context=self.context).data
        return None


# ============================================================================
# Enrollment & Progress Serializers
# ============================================================================

class LessonProgressSerializer(serializers.ModelSerializer):
    """Lesson progress tracking"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    
    class Meta:
        model = LessonProgress
        fields = [
            'id',
            'lesson',
            'lesson_title',
            'is_completed',
            'last_position_seconds',
            'total_time_spent',
            'completion_percentage',
            'first_accessed',
            'last_accessed',
            'completed_at',
        ]
        read_only_fields = ['id', 'first_accessed', 'last_accessed', 'completed_at']


class EnrollmentSerializer(serializers.ModelSerializer):
    """Student enrollment details"""
    course_id = serializers.IntegerField(source='course.id', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_thumbnail = serializers.SerializerMethodField()
    teacher_name = serializers.CharField(source='course.teacher.get_full_name', read_only=True)
    category_name = serializers.CharField(source='course.category.name', read_only=True)
    total_lessons = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Enrollment
        fields = [
            'id',
            'course',
            'course_id',
            'course_title',
            'course_thumbnail',
            'teacher_name',
            'category_name',
            'total_lessons',
            'status',
            'enrolled_at',
            'progress_percentage',
            'total_listening_time',
            'lessons_completed',
            'last_accessed',
        ]
        read_only_fields = ['id', 'enrolled_at', 'last_accessed']
    
    def get_course_thumbnail(self, obj):
        """Get course thumbnail URL"""
        if obj.course.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.course.thumbnail.url)
            return obj.course.thumbnail.url
        return None

    def get_total_lessons(self, obj):
        """Expose total lessons count on enrollment for frontend convenience"""
        # Prefer explicit enrollment value if present
        try:
            if getattr(obj, 'total_lessons', None):
                return int(obj.total_lessons)
        except Exception:
            pass

        # Fallback to course.total_lessons
        try:
            if obj.course and getattr(obj.course, 'total_lessons', None) is not None:
                return int(obj.course.total_lessons)
        except Exception:
            pass

        return 0

    def get_progress_percentage(self, obj):
        """Return progress as a native float for mobile clients"""
        try:
            val = getattr(obj, 'progress_percentage', 0) or 0
            # DecimalField -> convert to float safely
            return float(val)
        except Exception:
            return 0.0


class EnrollmentDetailSerializer(EnrollmentSerializer):
    """Detailed enrollment with progress tracking"""
    lesson_progress = LessonProgressSerializer(many=True, read_only=True)
    course_details = CourseListSerializer(source='course', read_only=True)
    
    class Meta(EnrollmentSerializer.Meta):
        fields = EnrollmentSerializer.Meta.fields + [
            'completed_at',
            'expires_at',
            'payment_amount',
            'lesson_progress',
            'course_details',
        ]


# ============================================================================
# Review Serializers
# ============================================================================

class ReviewSerializer(serializers.ModelSerializer):
    """Course review serializer"""
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id',
            'course',
            'student',
            'student_name',
            'student_email',
            'rating',
            'title',
            'comment',
            'is_approved',
            'created_at',
        ]
        read_only_fields = ['id', 'student', 'is_approved', 'created_at']


# ============================================================================
# Notification Serializers
# ============================================================================

class NotificationSerializer(serializers.ModelSerializer):
    """Notification serializer for mobile"""
    course_title = serializers.CharField(source='course.title', read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'title',
            'message',
            'link_url',
            'link_text',
            'course',
            'course_title',
            'lesson',
            'lesson_title',
            'is_read',
            'created_at',
            'read_at',
        ]
        read_only_fields = ['id', 'created_at', 'read_at']


# ============================================================================
# Payment Serializers
# ============================================================================

class PaymentSerializer(serializers.ModelSerializer):
    """Payment transaction serializer"""
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'course',
            'course_title',
            'amount',
            'currency',
            'status',
            'payment_method',
            'razorpay_order_id',
            'created_at',
            'completed_at',
        ]
        read_only_fields = ['id', 'created_at', 'completed_at']


class SubscriptionSerializer(serializers.ModelSerializer):
    """Subscription serializer"""
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id',
            'course',
            'course_title',
            'status',
            'interval',
            'amount',
            'currency',
            'start_date',
            'end_date',
            'next_billing_date',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ============================================================================
# Analytics Serializers
# ============================================================================

class ListeningSessionSerializer(serializers.ModelSerializer):
    """Listening session tracking"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    
    class Meta:
        model = ListeningSession
        fields = [
            'id',
            'lesson',
            'lesson_title',
            'session_id',
            'started_at',
            'ended_at',
            'duration_seconds',
            'start_position',
            'end_position',
            'completed',
        ]
        read_only_fields = ['id', 'started_at']


# ============================================================================
# Banner Serializers
# ============================================================================

class MobileBannerSerializer(serializers.ModelSerializer):
    """Banner serializer optimized for mobile"""
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Banner
        fields = [
            'id',
            'title',
            'description',
            'image_url',
            'button_text',
            'button_link',
            'banner_type',
        ]
    
    def get_image_url(self, obj):
        """Get banner image URL"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


# ============================================================================
# Search & Discovery Serializers
# ============================================================================

class CourseSearchSerializer(serializers.ModelSerializer):
    """Optimized serializer for search results"""
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'short_description',
            'teacher_name',
            'category_name',
            'thumbnail_url',
            'level',
            'price',
            'actual_price',
            'is_free',
            'average_rating',
        ]
    
    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None


# ============================================================================
# Certificate Serializers
# ============================================================================

class CertificateSerializer(serializers.ModelSerializer):
    """Certificate serializer for mobile"""
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_thumbnail = serializers.SerializerMethodField()
    certificate_url = serializers.SerializerMethodField()
    
    class Meta:
        from apps.courses.models import Certificate
        model = Certificate
        fields = [
            'id',
            'course',
            'course_title',
            'course_thumbnail',
            'certificate_number',
            'issued_date',
            'expiry_date',
            'certificate_url',
            'verification_code',
        ]
        read_only_fields = ['id', 'certificate_number', 'issued_date', 'verification_code']
    
    def get_course_thumbnail(self, obj):
        if obj.course.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.course.thumbnail.url)
            return obj.course.thumbnail.url
        return None
    
    def get_certificate_url(self, obj):
        if obj.certificate_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.certificate_file.url)
            return obj.certificate_file.url
        return None


# ============================================================================
# Download Serializers
# ============================================================================

class DownloadSerializer(serializers.ModelSerializer):
    """Download tracking serializer"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    lesson_duration = serializers.IntegerField(source='lesson.duration_seconds', read_only=True)
    audio_url = serializers.SerializerMethodField()
    
    class Meta:
        from apps.courses.models import Download
        model = Download
        fields = [
            'id',
            'lesson',
            'lesson_title',
            'lesson_duration',
            'audio_url',
            'status',
            'downloaded_at',
            'file_size',
        ]
        read_only_fields = ['id', 'downloaded_at']
    
    def get_audio_url(self, obj):
        if obj.lesson.audio_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.lesson.audio_file.url)
            return obj.lesson.audio_file.url
        return None
