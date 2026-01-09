"""
URL configuration for courses app
"""
from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Course Browsing
    path('', views.CourseListView.as_view(), name='course_list'),
    path('<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail'),
    
    # Enrollment
    path('<int:course_id>/enroll/', views.enroll_course, name='enroll_course'),
    
    # Learning Interface
    path('<int:course_id>/learn/', views.course_learn, name='course_learn'),
    path('lesson/<int:lesson_id>/', views.lesson_view, name='lesson_view'),
    path('lesson/<int:lesson_id>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),
    path('lesson/<int:lesson_id>/audio/', views.serve_lesson_audio, name='serve_lesson_audio'),
    
    # Notes
    path('lesson/<int:lesson_id>/note/', views.create_note, name='create_note'),
    path('note/<int:note_id>/delete/', views.delete_note, name='delete_note'),
    
    # Reviews
    path('<int:course_id>/review/', views.create_review, name='create_review'),
    
    # My Courses
    path('my/courses/', views.my_courses, name='my_courses'),
    
    # Teacher Course Management
    path('teacher/courses/', views.teacher_courses, name='teacher_courses'),
    path('teacher/courses/create/', views.teacher_course_create, name='teacher_course_create'),
    path('teacher/courses/<int:course_id>/edit/', views.teacher_course_edit, name='teacher_course_edit'),
    path('teacher/courses/<int:course_id>/delete/', views.teacher_course_delete, name='teacher_course_delete'),
    path('teacher/courses/<int:course_id>/students/', views.teacher_course_students, name='teacher_course_students'),
    path('teacher/courses/<int:course_id>/preview/', views.teacher_course_preview, name='teacher_course_preview'),
    path('teacher/courses/<int:course_id>/duplicate/', views.teacher_course_duplicate, name='teacher_course_duplicate'),
    path('teacher/analytics/', views.teacher_analytics, name='teacher_analytics'),
    
    # Teacher Students Management
    path('teacher/students/', views.teacher_students_list, name='teacher_students'),
    path('teacher/students/<int:enrollment_id>/', views.teacher_student_detail, name='teacher_student_detail'),
    
    # Teacher Reviews Management
    path('teacher/reviews/', views.teacher_reviews_list, name='teacher_reviews'),
    path('teacher/reviews/<int:review_id>/toggle-approval/', views.teacher_review_toggle_approval, name='teacher_review_toggle_approval'),
    
    # Bulk Operations
    path('teacher/courses/bulk-action/', views.teacher_bulk_course_action, name='teacher_bulk_course_action'),
    
    # Export Features
    path('teacher/export/students/', views.teacher_export_students, name='teacher_export_students'),
    path('teacher/export/earnings/', views.teacher_export_earnings, name='teacher_export_earnings'),
    
    # Module Management
    path('teacher/courses/<int:course_id>/module/create/', views.teacher_module_create, name='teacher_module_create'),
    path('teacher/module/<int:module_id>/edit/', views.teacher_module_edit, name='teacher_module_edit'),
    path('teacher/module/<int:module_id>/delete/', views.teacher_module_delete, name='teacher_module_delete'),
    path('teacher/courses/<int:course_id>/modules/reorder/', views.teacher_module_reorder, name='teacher_module_reorder'),
    
    # Lesson Management
    path('teacher/module/<int:module_id>/lesson/create/', views.teacher_lesson_create, name='teacher_lesson_create'),
    path('teacher/lesson/<int:lesson_id>/edit/', views.teacher_lesson_edit, name='teacher_lesson_edit'),
    path('teacher/lesson/<int:lesson_id>/delete/', views.teacher_lesson_delete, name='teacher_lesson_delete'),
    path('teacher/module/<int:module_id>/lessons/reorder/', views.teacher_lesson_reorder, name='teacher_lesson_reorder'),
    path('teacher/lesson-media/<int:media_id>/delete/', views.teacher_lesson_media_delete, name='teacher_lesson_media_delete'),
]
