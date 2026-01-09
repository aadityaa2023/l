"""
Context processors for notifications
"""
from apps.notifications.models import Notification, Message


def unread_counts(request):
    """Add unread counts to context"""
    if request.user.is_authenticated:
        return {
            'unread_notifications_count': Notification.objects.filter(
                user=request.user,
                is_read=False
            ).count(),
            'unread_messages_count': Message.objects.filter(
                recipient=request.user,
                is_read=False
            ).count(),
        }
    return {
        'unread_notifications_count': 0,
        'unread_messages_count': 0,
    }
