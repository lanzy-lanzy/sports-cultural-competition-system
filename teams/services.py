from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from accounts.access import MANAGEMENT_ROLES, get_user_role
from audit.models import record_action
from eligibility.models import EligibilityRecord
from participants.models import Participant
from sports.models import EventEntry, SportsEvent
from .models import Team, TeamMembership


def require_team_access(user, team):
    if get_user_role(user) in MANAGEMENT_ROLES:
        return
    if get_user_role(user) != 'TEAM_MANAGER' or not team.staff_assignments.filter(user=user).exists():
        raise PermissionDenied('You cannot manage this team.')


def available_member_events(team, participant=None):
    query = Q(team_based=True, entries__team=team, entries__status=EventEntry.Status.CONFIRMED)
    if participant is not None:
        query |= Q(team_based=False, entries__participant=participant, entries__status=EventEntry.Status.CONFIRMED)
    return SportsEvent.objects.filter(query).select_related('competition').distinct().order_by('competition__name', 'name')


def validate_member_events(membership, events):
    selected = {event.pk: event for event in events}
    current = {event.pk: event for event in membership.events.all()} if membership.pk else {}
    changed = set(selected) ^ set(current)
    participant = membership.participant
    allowed = set(available_member_events(membership.team, participant).values_list('pk', flat=True))
    for pk in changed:
        event = selected.get(pk) or current[pk]
        if event.confirmed_at or event.status in ('COMPLETED', 'CANCELLED') or event.competition.status in ('COMPLETED', 'CANCELLED'):
            raise ValidationError(f'{event.name}: this event is closed; its roster cannot be changed.')
        if pk not in selected:
            continue
        if pk not in allowed:
            raise ValidationError(f'{event.name}: a confirmed team or individual entry is required.')
        if membership.status != TeamMembership.Status.ACTIVE or participant.status != 'ACTIVE' or membership.team.status != Team.Status.APPROVED:
            raise ValidationError('Only active players on approved teams can be assigned to events.')
        if event.gender in ('male', 'female') and participant.gender != event.gender:
            raise ValidationError(f'{event.name}: the player does not meet the gender division.')
        if event.category != 'OPEN' and participant.category != event.category:
            raise ValidationError(f'{event.name}: the player does not meet the category division.')
        review = EligibilityRecord.objects.filter(participant=participant, competition=event.competition).first()
        if review and review.status != EligibilityRecord.Status.APPROVED:
            raise ValidationError(f'{event.name}: eligibility must be approved before assignment.')


@transaction.atomic
def set_member_events(membership, events, user):
    membership = TeamMembership.objects.select_for_update().select_related('team', 'participant').get(pk=membership.pk)
    require_team_access(user, membership.team)
    selected_ids = {event.pk for event in events}
    related_ids = selected_ids | set(membership.events.values_list('pk', flat=True))
    locked = {event.pk: event for event in SportsEvent.objects.select_for_update().select_related('competition').filter(pk__in=related_ids).order_by('pk')}
    if not selected_ids <= set(locked):
        raise ValidationError('An event was removed. Refresh the roster and try again.')
    events = [locked[pk] for pk in sorted(selected_ids)]
    validate_member_events(membership, events)
    membership.events.set(events)
    record_action(user, 'TEAM_MEMBERSHIP', target=membership.team,
                  details=f'Updated event assignments for {membership.participant.name}: ' + ', '.join(event.name for event in events))


@transaction.atomic
def force_delete_memberships(team, ids, user):
    team = Team.objects.select_for_update().get(pk=team.pk)
    require_team_access(user, team)
    members = list(TeamMembership.objects.select_for_update().filter(team=team, pk__in=ids).select_related('participant'))
    if not ids or len(members) != len(set(ids)):
        raise ValidationError('Select valid members belonging to this team.')
    names = [member.participant.name for member in members]
    participant_ids = [member.participant_id for member in members]
    Participant.objects.filter(pk__in=participant_ids, team_name=team.name).update(team_name='')
    TeamMembership.objects.filter(pk__in=[member.pk for member in members]).delete()
    record_action(user, 'TEAM_MEMBERSHIP', target=team,
                  details='Permanently removed roster memberships (player profiles retained): ' + ', '.join(names))
    return len(members)


@transaction.atomic
def force_delete_teams(ids, user):
    if get_user_role(user) not in MANAGEMENT_ROLES:
        raise PermissionDenied('Only competition management can permanently delete teams.')
    teams = list(Team.objects.select_for_update().filter(pk__in=ids))
    if not ids or len(teams) != len(set(ids)):
        raise ValidationError('Select valid teams.')
    from registrations.models import EventRegistration
    files = [(team.logo.storage, team.logo.name) for team in teams if team.logo]
    files.extend((registration.requirements_document.storage, registration.requirements_document.name)
                 for registration in EventRegistration.objects.filter(team__in=teams)
                 if registration.requirements_document)
    for team in teams:
        Participant.objects.filter(team_membership__team=team, team_name=team.name).update(team_name='')
        record_action(user, 'TEAM_MEMBERSHIP', details=f'Permanently deleted team {team.name} ({team.code}) and its roster and event entries.')
    # Django's collector performs hard deletion. PROTECT remains intact for published awards.
    Team.objects.filter(pk__in=ids).delete()
    # A protected-record failure rolls back the DB and never removes stored files.
    for storage, name in files:
        transaction.on_commit(lambda storage=storage, name=name: storage.delete(name), robust=True)
    return len(teams)
