from django.db import models, transaction

from .models import Participant, ParticipantCompetition


def _next_number(competition):
    """Return the next auto-incremented bib number for a competition."""
    highest = ParticipantCompetition.objects.filter(
        competition=competition
    ).aggregate(models.Max('number'))['number__max'] or 0
    return highest + 1


def _clean_ids(participant_ids):
    return [int(pid) for pid in participant_ids if str(pid).isdigit()]


@transaction.atomic
def assign_to_competition(competition, participant_ids):
    """Idempotently assign participants to a competition with auto-numbering.

    Returns the number of newly created assignments (already-assigned ids are
    silently skipped so the operation is safe to repeat).
    """
    ids = _clean_ids(participant_ids)
    if not ids:
        return 0

    already_assigned = set(
        ParticipantCompetition.objects.filter(
            competition=competition, participant_id__in=ids
        ).values_list('participant_id', flat=True)
    )
    new_ids = [pid for pid in ids if pid not in already_assigned]
    if not new_ids:
        return 0

    start_number = _next_number(competition)
    assignments = [
        ParticipantCompetition(
            participant_id=pid,
            competition=competition,
            number=start_number + offset,
        )
        for offset, pid in enumerate(new_ids)
    ]
    ParticipantCompetition.objects.bulk_create(assignments)
    return len(assignments)


@transaction.atomic
def unassign_from_competition(competition, participant_ids):
    """Remove participants from a competition. Returns the number removed."""
    ids = _clean_ids(participant_ids)
    if not ids:
        return 0
    ParticipantCompetition.objects.filter(
        competition=competition, participant_id__in=ids
    ).delete()
    return len(ids)


def assigned_rows(competition, query=''):
    """ParticipantCompetition rows for a competition, ordered by bib number."""
    rows = ParticipantCompetition.objects.filter(
        competition=competition
    ).select_related('participant')
    if query:
        rows = rows.filter(
            models.Q(participant__name__icontains=query)
            | models.Q(participant__email__icontains=query)
            | models.Q(participant__participant_id__icontains=query)
        )
    return rows.order_by('number')


def available_participants(competition, query=''):
    """Participants not yet assigned to the competition, ordered by name."""
    qs = Participant.objects.exclude(competitions=competition)
    if query:
        qs = qs.filter(
            models.Q(name__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(participant_id__icontains=query)
        )
    return qs.order_by('name')
