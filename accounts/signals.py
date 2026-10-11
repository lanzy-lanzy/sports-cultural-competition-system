from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        # Loading a fixture: the profile itself comes with the data.
        return
    if not created:
        return
    if instance.is_superuser:
        role = UserProfile.Role.ADMINISTRATOR
    elif instance.is_staff:
        role = UserProfile.Role.EVENT_ORGANIZER
    else:
        role = UserProfile.Role.SPECTATOR
    UserProfile.objects.get_or_create(user=instance, defaults={'role': role})


@receiver(post_save, sender='judges.Judge')
def mark_judge_role(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    if instance.user.is_superuser:
        return
    profile, _ = UserProfile.objects.get_or_create(user=instance.user)
    changed_fields = []
    if profile.role != UserProfile.Role.JUDGE:
        profile.role = UserProfile.Role.JUDGE
        changed_fields.append('role')
    if not profile.phone and instance.phone:
        profile.phone = instance.phone
        changed_fields.append('phone')
    if changed_fields:
        changed_fields.append('updated_at')
        profile.save(update_fields=changed_fields)

