from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from competitions.models import Competition
from eligibility.models import EligibilityRecord
from participants.models import Participant
from sports.models import EventEntry, SportsEvent, SportType
from .models import Team, TeamMembership, TeamStaff


class TeamEventRosterTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.client.force_login(self.admin)
        self.competition = Competition.objects.create(
            name='Campus Games', kind=Competition.Kind.SPORTS, status='ACTIVE',
            start_date=timezone.now(), end_date=timezone.now(), created_by=self.admin,
        )
        self.basketball = self.make_event('Basketball')
        self.volleyball = self.make_event('Volleyball')
        self.alex = Participant.objects.create(name='Alex Athlete', gender='male', status='ACTIVE')
        self.sam = Participant.objects.create(name='Sam Athlete', gender='male', status='ACTIVE')

    def make_event(self, name):
        sport = SportType.objects.create(name=name)
        return SportsEvent.objects.create(
            name=f'{name} Open Division', competition=self.competition, sport_type=sport,
        )

    def payload(self, basketball_players, volleyball_players):
        return {
            'name': 'Blue Warriors', 'category': Team.Category.SPORTS,
            'status': Team.Status.APPROVED,
            'sports_categories': [self.basketball.sport_type_id, self.volleyball.sport_type_id],
            'roster-event': [self.basketball.pk, self.volleyball.pk],
            f'event-players-{self.basketball.pk}': [player.pk for player in basketball_players],
            f'event-players-{self.volleyball.pk}': [player.pk for player in volleyball_players],
        }

    def test_create_and_edit_overlapping_event_rosters(self):
        response = self.client.get(reverse('create_team'))
        self.assertContains(response, 'Campus Games')
        self.assertContains(response, 'Basketball Open Division')
        self.assertContains(response, self.alex.participant_id)
        response = self.client.post(reverse('create_team'), self.payload([self.alex, self.sam], [self.alex]))
        team = Team.objects.get()
        self.assertRedirects(response, reverse('team_detail', args=[team.pk]))
        self.assertSetEqual(set(self.alex.team_membership.events.all()), {self.basketball, self.volleyball})
        self.assertSetEqual(set(self.sam.team_membership.events.all()), {self.basketball})
        self.assertEqual(team.event_entries.filter(status=EventEntry.Status.CONFIRMED).count(), 2)
        self.assertSetEqual(
            set(team.sports_categories.values_list('pk', flat=True)),
            {self.basketball.sport_type_id, self.volleyball.sport_type_id},
        )

        edit_url = reverse('edit_team', args=[team.pk])
        response = self.client.get(edit_url)
        self.assertContains(response, 'Sports event rosters')
        self.assertEqual(response.context['roster_form'][str(self.volleyball.pk)].value(), [self.alex.pk])
        response = self.client.post(edit_url, self.payload([], [self.alex, self.sam]))
        self.assertRedirects(response, reverse('team_detail', args=[team.pk]))
        self.assertSetEqual(set(self.sam.team_membership.events.all()), {self.volleyball})
        self.assertEqual(team.memberships.count(), 2)
        self.assertEqual(team.event_entries.count(), 2)

    def test_rejects_inactive_competition_submission(self):
        self.competition.status = 'DRAFT'
        self.competition.save(update_fields=['status'])
        self.assertNotContains(self.client.get(reverse('create_team')), 'Basketball Open Division')
        response = self.client.post(reverse('create_team'), self.payload([self.alex], []))
        self.assertContains(response, 'An event is no longer available')
        self.assertFalse(Team.objects.exists())

    def test_sports_team_requires_a_category(self):
        payload = self.payload([], [])
        payload.pop('sports_categories')
        response = self.client.post(reverse('create_team'), payload)
        self.assertContains(response, 'Select at least one sport for a Sports Team.')
        self.assertFalse(Team.objects.exists())

    def test_rejects_assignment_for_an_unselected_sport(self):
        payload = self.payload([], [self.alex])
        payload['sports_categories'] = [self.basketball.sport_type_id]
        response = self.client.post(reverse('create_team'), payload)
        self.assertContains(response, 'select its sport in Sports categories')
        self.assertFalse(Team.objects.exists())

    def test_workspace_saves_assignments_directly_for_selected_sports(self):
        team = Team.objects.create(
            name='Existing team', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        team.sports_categories.add(self.basketball.sport_type)
        workspace = reverse('team_detail', args=[team.pk])
        response = self.client.get(workspace)
        self.assertContains(response, 'Save assignments')
        self.assertContains(response, self.basketball.name)
        self.assertNotContains(response, self.volleyball.name)
        response = self.client.post(workspace, {
            'roster-event': [self.basketball.pk],
            f'event-players-{self.basketball.pk}': [self.alex.pk],
        })
        self.assertRedirects(response, workspace)
        self.assertTrue(team.memberships.get(participant=self.alex).events.filter(pk=self.basketball.pk).exists())
        self.assertEqual(team.event_entries.get().event, self.basketball)

    def test_workspace_can_remove_an_assignment_when_a_retained_entry_is_pending(self):
        team = Team.objects.create(
            name='Existing team', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        team.sports_categories.add(self.volleyball.sport_type)
        self.volleyball.team_based = False
        self.volleyball.save(update_fields=['team_based'])
        retained = TeamMembership.objects.create(team=team, participant=self.alex)
        removed = TeamMembership.objects.create(team=team, participant=self.sam)
        retained.events.add(self.volleyball)
        removed.events.add(self.volleyball)
        self.volleyball.entries.create(participant=self.alex, status=EventEntry.Status.PENDING)

        workspace = reverse('team_detail', args=[team.pk])
        response = self.client.post(workspace, {
            'roster-event': [self.volleyball.pk],
            f'event-players-{self.volleyball.pk}': [self.alex.pk],
        })
        self.assertRedirects(response, workspace)
        self.assertTrue(retained.events.filter(pk=self.volleyball.pk).exists())
        self.assertFalse(removed.events.exists())

    def test_individual_event_gets_an_entry_for_each_selected_player(self):
        self.volleyball.team_based = False
        self.volleyball.save(update_fields=['team_based'])
        response = self.client.post(reverse('create_team'), self.payload([], [self.alex, self.sam]))
        team = Team.objects.get()
        self.assertRedirects(response, reverse('team_detail', args=[team.pk]))
        self.assertSetEqual(
            set(self.volleyball.entries.values_list('participant_id', flat=True)),
            {self.alex.pk, self.sam.pk},
        )
        self.assertEqual(self.volleyball.assigned_team_members.filter(team=team).count(), 2)

    def test_ineligible_player_rolls_back_team_roster_and_entries(self):
        EligibilityRecord.objects.create(
            participant=self.alex, competition=self.competition, status=EligibilityRecord.Status.PENDING,
        )
        response = self.client.get(reverse('create_team'))
        player_field = response.context['roster_form'][str(self.basketball.pk)]
        self.assertIn('Eligibility approval required', str(player_field))
        options = list(player_field.field.widget.options(player_field.html_name, []))
        blocked = next(option for option in options if option['value'] == str(self.alex.pk))
        self.assertTrue(blocked['attrs']['disabled'])
        response = self.client.post(reverse('create_team'), self.payload([self.alex], [self.sam]))
        self.assertContains(response, 'eligibility must be approved before assignment')
        self.assertFalse(Team.objects.exists())
        self.assertFalse(TeamMembership.objects.exists())
        self.assertFalse(EventEntry.objects.exists())


class TeamManagementTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.manager = User.objects.create_user('manager', 'manager@example.com', 'pass')
        self.manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        self.manager.account_profile.save(update_fields=['role', 'updated_at'])
        self.participant = Participant.objects.create(
            name='Alex Athlete', email='athlete@example.com', phone='0917',
            age=20, gender='male', category='OPEN', status='ACTIVE',
        )

    def test_management_can_create_approved_team(self):
        self.client.force_login(self.admin)
        sport = SportType.objects.create(name='Basketball')
        response = self.client.post(reverse('create_team'), {
            'name': 'Blue Warriors', 'category': Team.Category.SPORTS,
            'description': 'College sports team', 'status': Team.Status.APPROVED,
            'sports_categories': [sport.pk],
        })

        team = Team.objects.get(name='Blue Warriors')
        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertTrue(team.code.startswith('TEAM-'))
        self.assertEqual(team.status, Team.Status.APPROVED)

    def test_team_manager_created_team_is_pending_and_owned(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('create_team'), {
            'name': 'Culture Guild', 'category': Team.Category.CULTURAL,
            'description': 'Cultural delegation',
        })

        team = Team.objects.get(name='Culture Guild')
        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertEqual(team.status, Team.Status.PENDING)
        self.assertTrue(TeamStaff.objects.filter(
            team=team, user=self.manager, role=TeamStaff.Role.MANAGER,
        ).exists())

    def test_assigned_manager_can_add_roster_member(self):
        team = Team.objects.create(
            name='Blue Warriors', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        TeamStaff.objects.create(team=team, user=self.manager, role=TeamStaff.Role.MANAGER)
        self.client.force_login(self.manager)

        response = self.client.post(reverse('add_team_member', args=[team.id]), {
            'participant': self.participant.id,
            'member_number': 12,
        })

        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertTrue(TeamMembership.objects.filter(
            team=team, participant=self.participant, member_number=12,
        ).exists())
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.team_name, 'Blue Warriors')

    def test_team_manager_cannot_access_unassigned_team(self):
        team = Team.objects.create(
            name='Other Team', category=Team.Category.MIXED,
            status=Team.Status.PENDING, created_by=self.admin,
        )
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('team_detail', args=[team.id])).status_code, 404)

    def test_management_can_assign_team_manager(self):
        team = Team.objects.create(
            name='Blue Warriors', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse('add_team_staff', args=[team.id]), {
            'user': self.manager.id,
            'role': TeamStaff.Role.COACH,
        })

        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertTrue(TeamStaff.objects.filter(
            team=team, user=self.manager, role=TeamStaff.Role.COACH,
        ).exists())

    def test_spectator_cannot_access_team_management(self):
        spectator = User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        self.client.force_login(spectator)
        self.assertEqual(self.client.get(reverse('team_list')).status_code, 403)


class AdminTeamApprovalTest(TestCase):
    """A team created by competition management is approved without a status step."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.organizer = User.objects.create_user('organizer', 'org@example.com', 'pass')
        self.organizer.account_profile.role = UserProfile.Role.EVENT_ORGANIZER
        self.organizer.account_profile.save(update_fields=['role', 'updated_at'])
        self.sport = SportType.objects.create(name='Volleyball')

    def _create(self, name):
        return self.client.post(reverse('create_team'), {
            'name': name, 'category': Team.Category.SPORTS,
            'description': 'Created in the workspace',
            'sports_categories': [self.sport.pk],
        })

    def test_admin_created_team_is_approved(self):
        self.client.force_login(self.admin)
        response = self._create('Green Wardens')
        team = Team.objects.get(name='Green Wardens')
        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertEqual(team.status, Team.Status.APPROVED)

    def test_create_form_omits_the_status_field(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('create_team'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="status"')
        # The missing control is explained rather than silently dropped.
        self.assertContains(response, 'approved automatically')

    def test_forged_pending_status_in_the_post_is_ignored(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('create_team'), {
            'name': 'Sneaky Squad', 'category': Team.Category.SPORTS,
            'status': Team.Status.PENDING,
            'sports_categories': [self.sport.pk],
        })
        self.assertEqual(
            Team.objects.get(name='Sneaky Squad').status,
            Team.Status.APPROVED,
        )

    def test_forged_suspended_status_is_ignored(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('create_team'), {
            'name': 'Sneakier Squad', 'category': Team.Category.SPORTS,
            'status': Team.Status.SUSPENDED,
            'sports_categories': [self.sport.pk],
        })
        self.assertEqual(
            Team.objects.get(name='Sneakier Squad').status,
            Team.Status.APPROVED,
        )

    def test_other_management_roles_are_auto_approved(self):
        self.client.force_login(self.organizer)
        self.client.post(reverse('create_team'), {
            'name': 'Organizer Crew', 'category': Team.Category.MIXED,
        })
        self.assertEqual(
            Team.objects.get(name='Organizer Crew').status,
            Team.Status.APPROVED,
        )

    def test_team_manager_still_submits_for_approval(self):
        manager = User.objects.create_user('mgr', 'mgr@example.com', 'pass')
        manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        manager.account_profile.save(update_fields=['role', 'updated_at'])
        self.client.force_login(manager)
        self.client.post(reverse('create_team'), {
            'name': 'Culture Guild', 'category': Team.Category.CULTURAL,
        })
        self.assertEqual(
            Team.objects.get(name='Culture Guild').status,
            Team.Status.PENDING,
        )

    def test_management_can_still_change_status_on_edit(self):
        self.client.force_login(self.admin)
        self._create('Blue Warriors')
        team = Team.objects.get(name='Blue Warriors')

        # Suspending an approved team must remain possible after creation.
        self.client.post(reverse('edit_team', args=[team.id]), {
            'name': team.name, 'category': team.category,
            'description': team.description, 'status': Team.Status.SUSPENDED,
        })
        team.refresh_from_db()
        self.assertEqual(team.status, Team.Status.SUSPENDED)

        # And approving it again.
        self.client.post(reverse('edit_team', args=[team.id]), {
            'name': team.name, 'category': team.category,
            'description': team.description, 'status': Team.Status.APPROVED,
        })
        team.refresh_from_db()
        self.assertEqual(team.status, Team.Status.APPROVED)

    def test_edit_form_still_shows_status(self):
        self.client.force_login(self.admin)
        self._create('Blue Warriors')
        team = Team.objects.get(name='Blue Warriors')
        response = self.client.get(reverse('edit_team', args=[team.id]))
        self.assertContains(response, 'name="status"')

    def test_approved_team_is_selectable_for_sport_entries(self):
        """Approval matters: only approved teams can enter sport events."""
        from competitions.models import Competition
        from sports.forms import EventEntryForm
        from sports.models import SportsEvent, SportType

        self.client.force_login(self.admin)
        self._create('Blue Warriors')
        team = Team.objects.get(name='Blue Warriors')

        competition = Competition.objects.create(
            name='Meet', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        event = SportsEvent.objects.create(
            competition=competition,
            sport_type=SportType.objects.create(name='Basketball', team_based=True),
            name='Basketball', team_based=True,
        )
        form = EventEntryForm(event=event)
        self.assertIn(team, form.fields['team'].queryset)


class TeamRosterSearchTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('roster-admin', '', 'pass')
        cls.team = Team.objects.create(name='SOCJE', category='SPORTS', created_by=cls.admin)
        cls.other_team = Team.objects.create(name='SAFES', category='SPORTS', created_by=cls.admin)
        cls.alex = Participant.objects.create(name='Alex Player', phone='0917', gender='male')
        cls.bella = Participant.objects.create(name='Bella Player', phone='0918', gender='female', category='JUNIOR')
        cls.outsider = Participant.objects.create(name='Alex Outside', phone='0919')
        TeamMembership.objects.create(team=cls.team, participant=cls.alex, member_number=12)
        TeamMembership.objects.create(team=cls.team, participant=cls.bella, member_number=7, status='INACTIVE')
        TeamMembership.objects.create(team=cls.other_team, participant=cls.outsider, member_number=12)

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse('team_detail', args=[self.team.pk])

    def test_default_roster_includes_active_and_inactive_members_only_for_team(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Alex Player')
        self.assertContains(response, 'Bella Player')
        self.assertNotContains(response, 'Alex Outside')
        self.assertEqual(response.context['total_members'], 2)
        self.assertContains(response, 'Inactive member')
        self.assertContains(response, self.alex.participant_id)

    def test_search_name_identifier_and_jersey_number(self):
        for query in ('  aLeX  ', self.alex.participant_id.lower(), '12'):
            with self.subTest(query=query):
                response = self.client.get(self.url, {'q': query})
                self.assertEqual([m.participant_id for m in response.context['memberships']], [self.alex.pk])
                self.assertEqual(response.context['total_members'], 2)

    def test_filters_combine_with_search(self):
        response = self.client.get(self.url, {
            'q': 'Player', 'status': 'INACTIVE', 'category': 'JUNIOR', 'gender': 'female',
        })
        self.assertEqual([m.participant_id for m in response.context['memberships']], [self.bella.pk])
        response = self.client.get(self.url, {'status': 'ACTIVE', 'gender': 'female'})
        self.assertContains(response, 'No players match these filters')
        self.assertEqual(response.context['page_obj'].paginator.count, 0)

    def test_invalid_filter_is_reported(self):
        response = self.client.get(self.url, {'status': 'unknown'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['filter_form'].errors)
        self.assertEqual(response.context['page_obj'].paginator.count, 0)

    def test_pagination_keeps_filters_and_handles_invalid_page(self):
        for index in range(26):
            participant = Participant.objects.create(name=f'Extra Player {index:02}', phone='0')
            TeamMembership.objects.create(team=self.team, participant=participant)
        response = self.client.get(self.url, {'q': 'Player', 'page': 'bad'})
        self.assertEqual(len(response.context['memberships']), 25)
        self.assertContains(response, '?q=Player&amp;page=2')
        response = self.client.get(self.url, {'q': 'Player', 'page': '999'})
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertEqual(len(response.context['memberships']), 3)

    def test_manager_can_search_assigned_team_but_not_other_teams(self):
        manager = User.objects.create_user('roster-manager', password='pass')
        manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        manager.account_profile.save()
        TeamStaff.objects.create(team=self.team, user=manager, role='MANAGER')
        self.client.force_login(manager)
        self.assertContains(self.client.get(self.url, {'q': 'Alex'}), 'Alex Player')
        response = self.client.get(reverse('team_detail', args=[self.other_team.pk]), {'q': 'Alex'})
        self.assertEqual(response.status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)


class TeamBulkAndEventsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from competitions.models import Competition
        from sports.models import EventEntry, SportsEvent, SportType
        cls.admin = User.objects.create_superuser('bulk-admin', '', 'pass')
        cls.manager = User.objects.create_user('bulk-manager', password='pass')
        cls.manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        cls.manager.account_profile.save()
        cls.team = Team.objects.create(name='Bulk Team', category='SPORTS', status='APPROVED', created_by=cls.admin)
        cls.other = Team.objects.create(name='Other Bulk Team', category='SPORTS', status='APPROVED', created_by=cls.admin)
        TeamStaff.objects.create(team=cls.team, user=cls.manager, role='MANAGER')
        cls.players = [Participant.objects.create(name=f'Player {i}', phone='0', gender='male', team_name=cls.team.name) for i in range(3)]
        cls.members = [TeamMembership.objects.create(team=cls.team, participant=p, member_number=i+1) for i,p in enumerate(cls.players[:2])]
        cls.competition = Competition.objects.create(name='Bulk meet', description='Meet', start_date='2026-12-01T08:00:00Z', end_date='2026-12-05T17:00:00Z', created_by=cls.admin, status='ACTIVE')
        cls.events = []
        for name in ('Basketball', 'Volleyball'):
            sport = SportType.objects.create(name=name)
            event = SportsEvent.objects.create(name=name, competition=cls.competition, sport_type=sport, team_based=True, gender='male')
            EventEntry.objects.create(event=event, team=cls.team, status='CONFIRMED')
            cls.events.append(event)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_member_bulk_preview_and_permanent_removal_retain_profiles(self):
        member = self.members[0]
        member.events.set(self.events)
        url = reverse('bulk_delete_members', args=[self.team.pk])
        selected = [m.pk for m in self.members]
        preview = self.client.post(url, {'selected': selected})
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, 'This cannot be undone')
        self.assertEqual(self.team.memberships.count(), 2)
        self.client.post(url, {'selected': selected, 'confirm':'yes'})
        self.assertFalse(self.team.memberships.exists())
        self.assertEqual(Participant.objects.count(), 3)
        self.assertFalse(TeamMembership.events.through.objects.exists())
        self.assertFalse(Participant.objects.filter(pk__in=[p.pk for p in self.players[:2]]).exclude(team_name='').exists())

    def test_bad_bulk_selection_cannot_partially_delete(self):
        url = reverse('bulk_delete_members', args=[self.team.pk])
        for selected in ([], ['oops'], [self.members[0].pk, 999999]):
            self.client.post(url, {'selected':selected,'confirm':'yes'})
        self.assertEqual(self.team.memberships.count(), 2)

    def test_bulk_team_delete_is_hard_and_cascades_memberships(self):
        from sports.models import EventEntry
        url = reverse('bulk_delete_teams')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {'selected':[self.team.pk,self.other.pk]})
        self.assertEqual(Team.objects.count(), 2)
        self.client.post(url, {'selected':[self.team.pk,self.other.pk],'confirm':'yes'})
        self.assertEqual(Team.objects.count(), 0)
        self.assertFalse(TeamMembership.objects.exists())
        self.assertFalse(EventEntry.objects.exists())
        self.assertEqual(Participant.objects.count(),3)

    def test_award_protection_rolls_back_entire_bulk_delete(self):
        from sports.models import EventAward, EventEntry
        EventAward.objects.create(event=self.events[0], entry=EventEntry.objects.get(event=self.events[0],team=self.team), medal='gold')
        self.client.post(reverse('bulk_delete_teams'), {'selected':[self.team.pk,self.other.pk], 'confirm':'yes'})
        self.assertEqual(Team.objects.count(),2)
        self.assertEqual(self.team.memberships.count(),2)
        self.players[0].refresh_from_db()
        self.assertEqual(self.players[0].team_name,self.team.name)

    def test_manager_access_and_csrf(self):
        from django.test import Client
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(reverse('bulk_delete_teams'),{'selected':[self.team.pk],'confirm':'yes'}).status_code,403)
        foreign_member = TeamMembership.objects.create(team=self.other,participant=self.players[2])
        self.client.post(reverse('bulk_delete_members',args=[self.team.pk]),{'selected':[self.members[0].pk,foreign_member.pk],'confirm':'yes'})
        self.assertEqual(TeamMembership.objects.count(),3)
        self.assertEqual(self.client.post(reverse('update_member_events',args=[self.other.pk,foreign_member.pk]),{}).status_code,404)
        csrf_client=Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(reverse('bulk_delete_teams'),{'selected':[self.team.pk],'confirm':'yes'}).status_code,403)

    def event_post(self, events):
        member=self.members[0]
        return self.client.post(reverse('update_member_events',args=[self.team.pk,member.pk]), {f'member-{member.pk}-events':[e.pk for e in events]})

    def test_assign_replace_and_clear_multiple_events(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.event_post(self.events).status_code,302)
        self.assertEqual(self.members[0].events.count(),2)
        self.assertEqual(self.event_post(self.events[:1]).status_code,302)
        self.assertEqual(self.members[0].events.count(),1)
        self.assertEqual(self.event_post([]).status_code,302)
        self.assertFalse(self.members[0].events.exists())

    def test_add_player_with_multiple_events(self):
        response=self.client.post(reverse('add_team_member',args=[self.team.pk]), {'participant':self.players[2].pk,'member_number':3,'events':[e.pk for e in self.events]})
        self.assertEqual(response.status_code,302)
        self.assertEqual(TeamMembership.objects.get(participant=self.players[2]).events.count(),2)

    def test_rejected_pending_eligibility_and_wrong_divisions_block_assignment(self):
        from eligibility.models import EligibilityRecord
        for status in ('PENDING','REJECTED'):
            EligibilityRecord.objects.update_or_create(participant=self.players[0],competition=self.competition,defaults={'status':status})
            self.assertEqual(self.event_post(self.events).status_code,400)
            self.assertEqual(self.members[0].events.count(),0)
        EligibilityRecord.objects.filter(participant=self.players[0]).update(status='APPROVED')
        self.events[1].gender='female'
        self.events[1].save()
        self.assertEqual(self.event_post(self.events).status_code,400)
        self.assertEqual(self.members[0].events.count(),0)
        self.events[1].gender='male'
        self.events[1].category='JUNIOR'
        self.events[1].save()
        self.assertEqual(self.event_post(self.events).status_code,400)

    def test_foreign_event_closed_event_and_inactive_member_are_rejected(self):
        from sports.models import EventEntry
        EventEntry.objects.filter(event=self.events[1],team=self.team).delete()
        self.assertEqual(self.event_post(self.events).status_code,400)
        self.events[0].status='COMPLETED'
        self.events[0].save()
        self.assertEqual(self.event_post(self.events[:1]).status_code,400)
        self.events[0].status='PLANNED'
        self.events[0].save()
        self.members[0].status='INACTIVE'
        self.members[0].save()
        self.assertEqual(self.event_post(self.events[:1]).status_code,400)

    def test_closed_assignments_are_displayed_and_cannot_be_removed(self):
        self.members[0].events.add(self.events[0])
        self.events[0].status='COMPLETED'
        self.events[0].save()
        response=self.client.get(reverse('team_detail',args=[self.team.pk]))
        self.assertContains(response,'Manage events')
        self.assertEqual(self.event_post([]).status_code,400)
        self.assertEqual(self.members[0].events.count(),1)

    def test_invalid_add_cannot_create_partial_membership(self):
        self.events[1].gender='female'
        self.events[1].save()
        self.client.post(reverse('add_team_member',args=[self.team.pk]), {'participant':self.players[2].pk,'member_number':3,'events':[e.pk for e in self.events]})
        self.assertFalse(TeamMembership.objects.filter(participant=self.players[2]).exists())

    def test_logo_cleanup_runs_after_successful_commit(self):
        from unittest.mock import patch
        self.team.logo='team_logos/bulk-test.png'
        self.team.save()
        with patch.object(Team._meta.get_field('logo').storage, 'delete') as delete:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(reverse('bulk_delete_teams'), {'selected':[self.team.pk],'confirm':'yes'})
            delete.assert_called_once_with('team_logos/bulk-test.png')


class DepartmentTeamManagerWorkflowTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('dept-admin', 'admin@example.com', 'pass')
        self.manager = User.objects.create_user('safes-mgr', 'safes@example.com', 'pass')
        self.manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        self.manager.account_profile.save(update_fields=['role', 'updated_at'])

        self.comp = Competition.objects.create(
            name='Intramurals 2026', description='Sports meet',
            kind=Competition.Kind.SPORTS, status='ACTIVE',
            start_date='2026-03-01T08:00:00Z', end_date='2026-03-05T17:00:00Z',
            created_by=self.admin,
        )
        self.basketball = SportType.objects.create(name='Dept Basketball', team_based=True)
        self.event = SportsEvent.objects.create(
            competition=self.comp, sport_type=self.basketball,
            name='Basketball Men', team_based=True,
            format=SportsEvent.Format.SINGLE_ELIMINATION,
            status=SportsEvent.Status.REGISTRATION,
        )

    def test_departments_and_full_team_manager_workflow(self):
        self.assertEqual(set(Team.Department.values), {'SAFES', 'SOCJE', 'STE', 'SCS'})

        # 1. Admin cannot create teams or register players.
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('create_team')).status_code, 403)
        self.assertEqual(self.client.get(reverse('create_participant')).status_code, 403)

        # 2. Team Manager submits department team registration -> PENDING.
        self.client.force_login(self.manager)
        resp = self.client.post(reverse('create_team'), {
            'department': Team.Department.SAFES,
            'name': 'SAFES Stallions',
            'category': Team.Category.SPORTS,
            'sports_categories': [self.basketball.pk],
        })
        team = Team.objects.get(name='SAFES Stallions')
        self.assertRedirects(resp, reverse('team_detail', args=[team.pk]))
        self.assertEqual(team.department, Team.Department.SAFES)
        self.assertEqual(team.status, Team.Status.PENDING)

        # 3. Pending team cannot register players, submit roster, or register for events.
        self.assertEqual(self.client.post(reverse('register_team_player', args=[team.pk]), {
            'first_name': 'Juan', 'last_name': 'Dela Cruz', 'phone': '09171234567',
            'gender': 'male', 'category': 'OPEN',
        }).status_code, 403)
        self.assertEqual(self.client.post(reverse('submit_team_roster', args=[team.pk])).status_code, 403)
        reg_resp = self.client.get(reverse('register_for_event'))
        self.assertNotIn('team', reg_resp.context['form'].fields)

        # 4. Admin can reject, then approve the department team.
        self.client.force_login(self.admin)
        self.client.post(reverse('update_team_status', args=[team.pk]), {'status': Team.Status.REJECTED})
        team.refresh_from_db()
        self.assertEqual(team.status, Team.Status.REJECTED)

        self.client.post(reverse('update_team_status', args=[team.pk]), {'status': Team.Status.APPROVED})
        team.refresh_from_db()
        self.assertEqual(team.status, Team.Status.APPROVED)

        # 5. Admin still cannot register players or mutate the approved team's roster.
        self.assertEqual(self.client.post(reverse('register_team_player', args=[team.pk]), {
            'first_name': 'Admin', 'last_name': 'Blocked', 'phone': '0917',
            'gender': 'male', 'category': 'OPEN',
        }).status_code, 403)

        # 6. Team Manager registers a player under the approved team and assigns sports event.
        self.client.force_login(self.manager)
        player_resp = self.client.post(reverse('register_team_player', args=[team.pk]), {
            'first_name': 'Juan', 'last_name': 'Dela Cruz', 'phone': '09171234567',
            'identification_number': '2026-001', 'age': 20,
            'gender': 'male', 'category': 'OPEN', 'member_number': 7,
            'events': [self.event.pk],
        })
        self.assertRedirects(player_resp, reverse('team_detail', args=[team.pk]))
        membership = TeamMembership.objects.get(team=team)
        self.assertEqual(membership.participant.name, 'Juan Dela Cruz')
        self.assertEqual(membership.member_number, 7)
        self.assertEqual(list(membership.events.all()), [self.event])

        # 7. Team Manager submits the final roster.
        submit_resp = self.client.post(reverse('submit_team_roster', args=[team.pk]))
        self.assertRedirects(submit_resp, reverse('team_detail', args=[team.pk]))
        team.refresh_from_db()
        self.assertTrue(team.roster_submitted)
        self.assertEqual(team.roster_submitted_by, self.manager)
        self.assertIsNotNone(team.roster_submitted_at)

        # 8. Approved team can now register for the sport event.
        event_reg_resp = self.client.post(reverse('register_for_event'), {
            'target_type': 'sport_event',
            'sport_event': str(self.event.pk),
            'team': team.pk,
        })
        self.assertRedirects(event_reg_resp, reverse('my_registrations'))

        # 9. Admin verifies submitted roster in read-only mode (no Register/Add/Remove forms).
        self.client.force_login(self.admin)
        verify_resp = self.client.get(reverse('team_detail', args=[team.pk]))
        self.assertEqual(verify_resp.status_code, 200)
        self.assertContains(verify_resp, 'Roster Submitted')
        self.assertContains(verify_resp, 'Juan Dela Cruz')
        self.assertContains(verify_resp, 'Basketball Men')
        self.assertNotContains(verify_resp, 'Register new player')
        self.assertNotContains(verify_resp, 'Remove player')

    def test_admin_receives_department_team_submission_and_sidebar_badges(self):
        from announcements.models import Notification

        # Team Manager submits a department team registration.
        self.client.force_login(self.manager)
        self.client.post(reverse('create_team'), {
            'department': Team.Department.SCS,
            'name': 'SCS Wizards',
            'category': Team.Category.SPORTS,
            'sports_categories': [self.basketball.pk],
        })
        team = Team.objects.get(name='SCS Wizards')

        # Admin receives an in-app notification pointing to the review queue.
        admin_notifs = Notification.objects.filter(recipient=self.admin, is_read=False)
        self.assertTrue(admin_notifs.filter(title='New department team registration').exists())

        # Admin sees the pending department team inside Registration Review Queue
        # and sees sidebar counter badges for pending registrations.
        self.client.force_login(self.admin)
        queue_resp = self.client.get(reverse('registration_review_queue'))
        self.assertEqual(queue_resp.status_code, 200)
        self.assertContains(queue_resp, 'Department Team Registrations Pending Approval')
        self.assertContains(queue_resp, 'SCS Wizards')
        self.assertEqual(queue_resp.context['pending_team_registrations'], 1)
        self.assertEqual(queue_resp.context['pending_registrations_total'], 1)
        self.assertEqual(queue_resp.context['pending_count'], 1)

        # Approving directly from Registration Review Queue redirects back, clears badges,
        # and notifies the Team Manager.
        approve_resp = self.client.post(reverse('update_team_status', args=[team.pk]), {
            'status': Team.Status.APPROVED,
            'next': 'registration_review_queue',
        })
        self.assertRedirects(approve_resp, reverse('registration_review_queue'))
        team.refresh_from_db()
        self.assertEqual(team.status, Team.Status.APPROVED)

        after_resp = self.client.get(reverse('registration_review_queue'))
        self.assertEqual(after_resp.context['pending_team_registrations'], 0)
        self.assertEqual(after_resp.context['pending_registrations_total'], 0)
        self.assertNotContains(after_resp, 'Department Team Registrations Pending Approval')
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.manager,
                title='Team registration approved',
            ).exists()
        )

    def test_admin_can_add_departments_and_approved_department_cannot_be_reselected(self):
        from teams.models import Department

        # Admin adds a new department (SBA) beyond the default 4.
        self.client.force_login(self.admin)
        add_resp = self.client.post(reverse('department_manage'), {
            'code': 'sba',
            'name': 'School of Business Administration',
        })
        self.assertRedirects(add_resp, reverse('department_manage'))
        self.assertTrue(Department.objects.filter(code='SBA', is_active=True).exists())

        # Create an APPROVED team for SAFES.
        Team.objects.create(
            name='SAFES Approved',
            department='SAFES',
            category=Team.Category.SPORTS,
            status=Team.Status.APPROVED,
            created_by=self.manager,
        )

        # Team Manager opening create_team sees SBA selectable, but SAFES is excluded & locked.
        self.client.force_login(self.manager)
        form_resp = self.client.get(reverse('create_team'))
        self.assertEqual(form_resp.status_code, 200)
        choice_codes = [code for code, _ in form_resp.context['form'].fields['department'].choices]
        self.assertIn('SBA', choice_codes)
        self.assertNotIn('SAFES', choice_codes)
        self.assertContains(form_resp, 'Already approved (locked)')

        # Submitting SAFES again via POST is rejected.
        blocked_resp = self.client.post(reverse('create_team'), {
            'department': 'SAFES',
            'name': 'Duplicate SAFES Team',
            'category': Team.Category.SPORTS,
            'sports_categories': [self.basketball.pk],
        })
        self.assertEqual(blocked_resp.status_code, 200)
        self.assertFalse(Team.objects.filter(name='Duplicate SAFES Team').exists())

        # Submitting the newly added SBA department succeeds.
        ok_resp = self.client.post(reverse('create_team'), {
            'department': 'SBA',
            'name': 'SBA Eagles',
            'category': Team.Category.SPORTS,
            'sports_categories': [self.basketball.pk],
        })
        self.assertEqual(ok_resp.status_code, 302)
        self.assertTrue(Team.objects.filter(name='SBA Eagles', department='SBA', status=Team.Status.PENDING).exists())

    def test_player_assignment_rbac_isolates_players_per_team_manager(self):
        other_mgr = User.objects.create_user('ste-mgr', 'ste@example.com', 'pass')
        other_mgr.account_profile.role = UserProfile.Role.TEAM_MANAGER
        other_mgr.account_profile.save(update_fields=['role', 'updated_at'])

        bulls = Team.objects.create(
            name='BULLS RBAC', department='SAFES', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.manager,
        )
        bulls.sports_categories.add(self.basketball)
        TeamStaff.objects.create(team=bulls, user=self.manager, role=TeamStaff.Role.MANAGER)

        phoenix = Team.objects.create(
            name='PHOENIX RBAC', department='STE', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=other_mgr,
        )
        phoenix.sports_categories.add(self.basketball)
        TeamStaff.objects.create(team=phoenix, user=other_mgr, role=TeamStaff.Role.MANAGER)

        bulls_player = Participant.objects.create(name='Bulls Star', phone='09170001', gender='male', status='ACTIVE', team_name=bulls.name)
        phoenix_player = Participant.objects.create(name='Phoenix Star', phone='09170002', gender='male', status='ACTIVE', team_name=phoenix.name)
        unassigned_player = Participant.objects.create(name='Global Free Agent', phone='09170003', gender='male', status='ACTIVE')

        bulls_member = TeamMembership.objects.create(team=bulls, participant=bulls_player, member_number=1)
        phoenix_member = TeamMembership.objects.create(team=phoenix, participant=phoenix_player, member_number=2)

        # SAFES manager only sees Bulls Star in Assign Players — never Phoenix Star or Global Free Agent.
        self.client.force_login(self.manager)
        resp = self.client.get(reverse('team_detail', args=[bulls.pk]))
        self.assertEqual(resp.status_code, 200)
        event_field = resp.context['roster_form'].fields[str(self.event.pk)]
        choice_ids = {int(val) for val, _ in event_field.choices}
        self.assertEqual(choice_ids, {bulls_player.pk})
        self.assertNotIn(phoenix_player.pk, choice_ids)
        self.assertNotIn(unassigned_player.pk, choice_ids)

        # Forged POST attempting to assign Phoenix Star or Global Free Agent to BULLS is rejected.
        for foreign_player in (phoenix_player, unassigned_player):
            forged = self.client.post(reverse('team_detail', args=[bulls.pk]), {
                'roster-event': [str(self.event.pk)],
                f'event-players-{self.event.pk}': [str(foreign_player.pk)],
            })
            self.assertEqual(forged.status_code, 400)
            self.assertFalse(TeamMembership.objects.filter(team=bulls, participant=foreign_player).exists())

        # SAFES manager cannot access PHOENIX workspace or mutate PHOENIX players.
        self.assertEqual(self.client.get(reverse('team_detail', args=[phoenix.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('remove_team_member', args=[phoenix.pk, phoenix_member.pk])).status_code, 404)

        # Assigning Bulls Star to BULLS succeeds cleanly.
        ok = self.client.post(reverse('team_detail', args=[bulls.pk]), {
            'roster-event': [str(self.event.pk)],
            f'event-players-{self.event.pk}': [str(bulls_player.pk)],
        })
        self.assertRedirects(ok, reverse('team_detail', args=[bulls.pk]))
        self.assertTrue(bulls_member.events.filter(pk=self.event.pk).exists())
