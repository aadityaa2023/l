from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, StudentProfile, TeacherProfile

# allauth signal to mark email verification on the User model
try:
    from allauth.account.signals import email_confirmed
except Exception:
    email_confirmed = None


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create profile when a new user is created
    """
    if created:
        if instance.role == 'student':
            StudentProfile.objects.create(user=instance)
        elif instance.role == 'teacher':
            # Teacher profiles are created by admin, so we don't auto-create
            pass


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save user profile when user is saved
    """
    if instance.role == 'student' and hasattr(instance, 'student_profile'):
        instance.student_profile.save()
    elif instance.role == 'teacher' and hasattr(instance, 'teacher_profile'):
        instance.teacher_profile.save()


if email_confirmed:
    @receiver(email_confirmed)
    def mark_user_email_verified(request, email_address, **kwargs):
        """
        When allauth confirms an email address, set the `email_verified`
        flag on the related `User` model so project code can read a single
        boolean instead of relying on allauth's EmailAddress model.
        """
        try:
            user = getattr(email_address, 'user', None)
            if user:
                user.email_verified = True
                user.save(update_fields=['email_verified'])
        except Exception:
            # Be defensive: don't let signal errors break account flows
            pass
