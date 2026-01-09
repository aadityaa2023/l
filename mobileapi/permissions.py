"""
Custom permissions for Mobile API
"""
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        if hasattr(obj, 'student'):
            return obj.student == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsEnrolledInCourse(permissions.BasePermission):
    """
    Check if user is enrolled in the course
    """
    
    def has_object_permission(self, request, view, obj):
        from apps.courses.models import Enrollment, Lesson, Course
        
        # Determine the course
        if isinstance(obj, Course):
            course = obj
        elif isinstance(obj, Lesson):
            course = obj.course
        else:
            return False
        
        # Check for free preview
        if isinstance(obj, Lesson) and obj.is_free_preview:
            return True
        
        # Check enrollment
        if request.user.is_authenticated:
            return Enrollment.objects.filter(
                student=request.user,
                course=course,
                status='active'
            ).exists()
        
        return False


class IsStudentUser(permissions.BasePermission):
    """
    Check if user is a student
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'student'


class IsTeacherUser(permissions.BasePermission):
    """
    Check if user is a teacher
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'teacher'
