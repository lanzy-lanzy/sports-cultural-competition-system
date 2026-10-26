from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = 'LOGIN', 'Login'
        ACCESS_UPDATED = 'ACCESS_UPDATED', 'Access updated'
        SCORE_SUBMIT = 'SCORE_SUBMIT', 'Scores submitted'
        SCORE_CHANGE = 'SCORE_CHANGE', 'Score changed'
        RESULT_VERIFIED = 'RESULT_VERIFIED', 'Round results verified'
        RANKINGS_CALCULATED = 'RANKINGS_CALCULATED', 'Rankings calculated'
        RESULTS_VISIBILITY = 'RESULTS_VISIBILITY', 'Results visibility changed'
        MATCH_RESULT = 'MATCH_RESULT', 'Match result recorded'
        BRACKET_GENERATED = 'BRACKET_GENERATED', 'Bracket generated'
        BRACKET_CLEARED = 'BRACKET_CLEARED', 'Bracket cleared'
        REGISTRATION_REVIEW = 'REGISTRATION_REVIEW', 'Registration reviewed'
        REGISTRATION_DELETED = 'REGISTRATION_DELETED', 'Registration deleted'
        ELIGIBILITY_REVIEW = 'ELIGIBILITY_REVIEW', 'Eligibility reviewed'
        ANNOUNCEMENT_PUBLISH = 'ANNOUNCEMENT_PUBLISH', 'Announcement published'
        AWARD_CHANGE = 'AWARD_CHANGE', 'Award changed'
        TEAM_STATUS = 'TEAM_STATUS', 'Team status changed'
        TEAM_MEMBERSHIP = 'TEAM_MEMBERSHIP', 'Team membership changed'
        PROTEST_REVIEW = 'PROTEST_REVIEW', 'Protest reviewed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'competition_app_auditlog'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['action']),
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.get_action_display()} - {self.user} - {self.created_at:%Y-%m-%d %H:%M}'

    @property
    def target_label(self):
        if self.content_object is not None:
            return str(self.content_object)[:200]
        return ''

    @property
    def target_model_name(self):
        return self.content_type.model_class()._meta.verbose_name if self.content_type else ''


def record_action(user, action, target=None, details='', ip_address=None):
    """Create an audit log entry. Safe to call anywhere; never raises."""
    entry = AuditLog(
        user=user if (user is not None and user.is_authenticated) else None,
        action=action,
        details=details or '',
        ip_address=ip_address,
    )
    if target is not None:
        from django.contrib.contenttypes.models import ContentType
        entry.content_type = ContentType.objects.get_for_model(target)
        entry.object_id = target.pk
    entry.save()
    return entry


def record_action_from_request(request, action, target=None, details=''):
    return record_action(
        request.user,
        action,
        target=target,
        details=details,
        ip_address=request.META.get('REMOTE_ADDR'),
    )