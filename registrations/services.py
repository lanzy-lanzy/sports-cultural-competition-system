from django.db import transaction
from django.utils import timezone

from participants.models import ParticipantCompetition
from sports.models import EventEntry

from .models import EventRegistration


def registrations_for_user(user):
    """Managers see current team submissions from every staff member; individuals see their own."""
    from accounts.access import get_user_role
    from accounts.models import UserProfile
    from django.db.models import Q
    from teams.models import Team
    registrations = EventRegistration.objects.all()
    if get_user_role(user) == UserProfile.Role.TEAM_MANAGER:
        team_ids = Team.objects.filter(staff_assignments__user=user).values('pk')
        return registrations.filter(Q(team_id__in=team_ids) | Q(team__isnull=True, registrant=user))
    return registrations.filter(registrant=user)


@transaction.atomic
def approve_registration(registration, reviewer, admin_notes=''):
    if registration.sport_event_id:
        from sports.models import SportsEvent
        event = SportsEvent.objects.select_for_update().get(pk=registration.sport_event_id)
        if event.matches.exists() or event.status in ('COMPLETED', 'CANCELLED'):
            raise ValueError('Registration is closed because event fixtures are locked.')
    registration.status = EventRegistration.Status.APPROVED
    registration.reviewed_by = reviewer
    registration.reviewed_at = timezone.now()
    if admin_notes:
        registration.notes = admin_notes
    registration.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'notes'])

    bracket_generated = False
    if registration.sport_event_id:
        event = registration.sport_event
        if bool(registration.team_id) != event.team_based:
            raise ValueError('The registration contestant type does not match the event.')
        if event.max_teams and event.entries.exclude(status='WITHDRAWN').count() >= event.max_teams:
            raise ValueError('The event has reached its entry cap.')
        entry, _ = EventEntry.objects.get_or_create(
            event=registration.sport_event,
            team=registration.team,
            participant=registration.participant,
            defaults={'status': EventEntry.Status.CONFIRMED},
        )
        if entry.status != EventEntry.Status.CONFIRMED:
            entry.status = EventEntry.Status.CONFIRMED
            entry.save(update_fields=['status'])
    elif registration.participant_id and registration.competition_id:
        if not ParticipantCompetition.objects.filter(
            participant=registration.participant,
            competition=registration.competition,
        ).exists():
            next_number = (
                ParticipantCompetition.objects.filter(competition=registration.competition)
                .order_by('-number')
                .values_list('number', flat=True)
                .first()
            )
            next_number = (next_number or 0) + 1
            ParticipantCompetition.objects.create(
                participant=registration.participant,
                competition=registration.competition,
                number=next_number,
            )

    from announcements.services import notify_users
    notify_users(
        [registration.registrant],
        title='Registration approved',
        body=f'Your registration for {registration.target_name} has been approved.',
        link='',
    )

    return bracket_generated


@transaction.atomic
def start_review(registration, reviewer):
    registration.status = EventRegistration.Status.UNDER_REVIEW
    registration.reviewed_by = reviewer
    registration.save(update_fields=['status', 'reviewed_by'])

    from announcements.services import notify_users
    notify_users(
        [registration.registrant],
        title='Registration under review',
        body=f'Your registration for {registration.target_name} is now under review.',
        link='',
    )


@transaction.atomic
def reject_registration(registration, reviewer, admin_notes=''):
    registration.status = EventRegistration.Status.REJECTED
    registration.reviewed_by = reviewer
    registration.reviewed_at = timezone.now()
    if admin_notes:
        registration.notes = admin_notes
    registration.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'notes'])

    from announcements.services import notify_users
    notify_users(
        [registration.registrant],
        title='Registration rejected',
        body=f'Your registration for {registration.target_name} was not approved.'
             + (f' Reason: {admin_notes}' if admin_notes else ''),
        link='',
    )


@transaction.atomic
def delete_registration(registration):
    """Permanently remove a registration from the review queue.

    Deletes any attached requirements document from storage before removing the
    record so no orphaned files are left behind.
    """
    if registration.requirements_document and registration.requirements_document.name:
        registration.requirements_document.delete(save=False)
    registration.delete()


@transaction.atomic
def force_delete_registration_template(template):
    """Permanently delete a registration template and its associated files.

    Bypasses any protection that would otherwise prevent deletion, satisfying
    the 'force delete' requirement. Audits the action immediately.
    """
    from audit.models import record_action

    template_id = template.id

    # Delete the requirements document file from storage
    if template.requirements_document and template.requirements_document.name:
        template.requirements_document.delete(save=False)

    # Permanent delete of the template record using parent's delete() directly
    # to bypass the overridden delete() in RegistrationTemplate (avoids recursion)
    RegistrationTemplate = template.__class__
    super(RegistrationTemplate, template).delete()

    record_action(
        template.created_by if hasattr(template, 'created_by') else None,
        'TEMPLATE_DELETED',
        target=template,
        details=f'Force deleted registration template: {template.name}',
    )


@transaction.atomic
def soft_delete_registration_template(template):
    """Mark a template as archived without removing the record (soft delete)."""
    from .models import RegistrationTemplate
    template.status = RegistrationTemplate.Status.ARCHIVED
    template.save(update_fields=['status'])
