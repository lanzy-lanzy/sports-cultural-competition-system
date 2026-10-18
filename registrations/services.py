from django.db import transaction
from django.utils import timezone

from participants.models import ParticipantCompetition
from sports.models import EventEntry

from .models import EventRegistration


@transaction.atomic
def approve_registration(registration, reviewer, admin_notes=''):
    registration.status = EventRegistration.Status.APPROVED
    registration.reviewed_by = reviewer
    registration.reviewed_at = timezone.now()
    if admin_notes:
        registration.notes = admin_notes
    registration.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'notes'])

    bracket_generated = False
    if registration.sport_event_id:
        event = registration.sport_event
        EventEntry.objects.get_or_create(
            event=registration.sport_event,
            team=registration.team,
            participant=registration.participant,
            defaults={'status': EventEntry.Status.CONFIRMED},
        )
        # Matches only exist once a bracket is generated. Auto-generate it when
        # this approval gives the event enough confirmed entries and no bracket
        # exists yet; keep any existing bracket intact to protect results.
        from sports.services import maybe_auto_generate_bracket
        if maybe_auto_generate_bracket(event):
            bracket_generated = True
            from audit.models import record_action
            record_action(
                reviewer,
                'BRACKET_GENERATED',
                target=event,
                details=f'Bracket auto-generated for {event.name} after registration approval',
            )
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
