"""
URL configuration for notifications app
"""
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Notifications
    path('', views.notifications_list, name='notifications_list'),
    path('<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('api/unread-count/', views.get_unread_notifications_count, name='get_unread_count'),
    
    # Messages
    path('messages/', views.messages_inbox, name='messages_inbox'),
    path('messages/<int:message_id>/', views.message_detail, name='message_detail'),
    path('messages/compose/', views.message_compose, name='message_compose'),
    path('messages/compose/<int:student_id>/', views.message_compose, name='message_compose_to'),
    
    # Q&A
    path('questions/', views.teacher_questions_list, name='teacher_questions'),
    path('questions/<int:question_id>/', views.question_detail, name='question_detail'),
    path('questions/answer/<int:answer_id>/mark-best/', views.mark_best_answer, name='mark_best_answer'),
    
    # Student Q&A
    path('student/questions/', views.student_questions_list, name='student_questions'),
    path('student/questions/ask/', views.student_ask_question, name='student_ask_question'),
    path('student/questions/ask/<int:lesson_id>/', views.student_ask_question, name='student_ask_question_lesson'),
    
    # Student Messages
    path('student/messages/', views.student_messages_inbox, name='student_messages'),
    path('student/messages/compose/', views.student_message_compose_to_teacher, name='student_message_compose'),
    path('student/messages/compose/<int:teacher_id>/', views.student_message_compose_to_teacher, name='student_message_compose_to'),
]
