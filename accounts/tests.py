from datetime import timedelta
from html.parser import HTMLParser

from django.contrib.auth.models import AnonymousUser, User
from django.core import mail
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from competitions.models import Competition
from judges.models import Judge, JudgeAssignment
from .context_processors import NAV_GROUPS, active_nav
from .models import UserProfile


class AccountTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')

    def test_register_creates_judge_and_redirects(self):
        resp = self.client.post(reverse('register'), {
            'username': 'newjudge', 'email': 'n@a.com',
            'password1': 'A-Strong-Competition-Pass-928!',
            'password2': 'A-Strong-Competition-Pass-928!',
            'first_name': 'Jane', 'middle_name': 'M.', 'last_name': 'Doe',
            'phone': '123', 'role': 'JUDGE',
        })
        self.assertRedirects(resp, reverse('login'))
        self.assertTrue(Judge.objects.filter(user__username='newjudge').exists())
        profile = UserProfile.objects.get(user__username='newjudge')
        self.assertEqual(profile.role, UserProfile.Role.JUDGE)
        self.assertEqual(profile.user.first_name, 'Jane')
        self.assertEqual(profile.user.last_name, 'Doe')
        self.assertEqual(profile.middle_name, 'M.')

    def test_public_registration_rejects_management_roles(self):
        resp = self.client.post(reverse('register'), {
            'username': 'organizer', 'email': 'organizer@example.com',
            'password1': 'A-Strong-Competition-Pass-928!',
            'password2': 'A-Strong-Competition-Pass-928!',
            'first_name': 'Event', 'last_name': 'Organizer', 'phone': '123',
            'role': UserProfile.Role.EVENT_ORGANIZER,
        })

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='organizer').exists())
        self.assertContains(resp, 'Select a valid choice')

    def test_landing_page_has_institutional_branding_and_primary_actions(self):
        resp = self.client.get(reverse('landing_page'))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'images/jhcsc_logo.png')
        self.assertContains(resp, 'images/it_logo.jpg')
        self.assertContains(resp, reverse('login'))
        self.assertContains(resp, reverse('register'))
        self.assertContains(resp, 'Every score counted.')

    def test_auth_pages_share_institutional_branding(self):
        for route_name in ('login', 'register'):
            with self.subTest(route_name=route_name):
                resp = self.client.get(reverse(route_name))
                self.assertContains(resp, 'images/jhcsc_logo.png')
                self.assertContains(resp, 'images/it_logo.jpg')
                self.assertContains(resp, reverse('landing_page'))

    def test_invalid_login_shows_a_clear_error(self):
        resp = self.client.post(reverse('login'), {
            'username': 'missing-user',
            'password': 'incorrect-password',
        })

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid username or password. Please try again.')

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_login_redirects_admin_to_dashboard(self):
        resp = self.client.post(reverse('login'), {'username': 'admin', 'password': 'pass'})
        self.assertRedirects(resp, reverse('dashboard'))

    def test_edit_profile_updates_account_details(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('edit_profile'), {
            'first_name': 'System', 'middle_name': 'Q', 'last_name': 'Administrator',
            'username': 'admin', 'email': 'new@a.com', 'phone': '09170000000',
        })
        self.assertRedirects(resp, reverse('edit_profile'))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.get_full_name(), 'System Administrator')
        self.assertEqual(self.admin.account_profile.middle_name, 'Q')
        self.assertEqual(self.admin.account_profile.phone, '09170000000')

    def test_login_redirects_spectator_to_portal(self):
        User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        resp = self.client.post(reverse('login'), {'username': 'viewer', 'password': 'pass'})
        self.assertRedirects(resp, reverse('portal_home'))

    def test_spectator_cannot_open_management_routes(self):
        viewer = User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('create_competition')).status_code, 403)
        self.assertEqual(self.client.get(reverse('participant_management')).status_code, 403)

    def test_administrator_can_change_user_role_and_status(self):
        target = User.objects.create_user('coordinator', 'c@example.com', 'pass')
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('update_user_access', args=[target.id]), {
            'role': UserProfile.Role.SPORTS_COORDINATOR,
            'is_active': 'on',
        })

        self.assertRedirects(resp, reverse('user_management') + '?page=1')
        target.refresh_from_db()
        self.assertEqual(target.account_profile.role, UserProfile.Role.SPORTS_COORDINATOR)
        self.assertTrue(target.is_staff)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_recovery_link(self):
        User.objects.create_user('recover', 'recover@example.com', 'pass')
        resp = self.client.post(reverse('password_reset'), {'email': 'recover@example.com'})

        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/password-reset/', mail.outbox[0].body)

    def test_participant_sidebar_omits_removed_workspace_actions(self):
        participant = User.objects.create_user('contestant', 'c@example.com', 'pass')
        UserProfile.objects.filter(user=participant).update(role=UserProfile.Role.PARTICIPANT)
        self.client.force_login(participant)
        resp = self.client.get(reverse('portal_home'))

        self.assertContains(resp, '<span>Participant Profile</span>')
        for label in ('Eligibility', 'Announcements', 'Submit Protest'):
            self.assertNotContains(resp, f'<span>{label}</span>')

    def test_team_manager_sidebar_keeps_shared_workspace_actions(self):
        manager = User.objects.create_user('skipper', 'm@example.com', 'pass')
        UserProfile.objects.filter(user=manager).update(role=UserProfile.Role.TEAM_MANAGER)
        self.client.force_login(manager)
        resp = self.client.get(reverse('portal_home'))

        self.assertContains(resp, '<span>Announcements</span>')
        self.assertContains(resp, '<span>Submit Protest</span>')


class NavigationContextTests(SimpleTestCase):
    def test_route_names_belong_to_only_one_navigation_group(self):
        names = [name for group in NAV_GROUPS.values() for name in group]
        self.assertEqual(len(names), len(set(names)))

    def test_resolved_routes_select_their_own_navigation_group(self):
        routes = [
            ('results_list', [], 'results'),
            ('competition_results_detail', [17], 'results'),
            ('results_print', [17], 'results'),
            ('round_results', [17, 3], 'results'),
            ('overall_medal_tally', [], 'medal_tally'),
            ('medal_tally', [17], 'medal_tally'),
            ('award_list', [17], 'awards'),
            ('reports_home', [], 'reports'),
            ('export_medal_tally_csv', [], 'reports'),
            ('print_medal_tally', [], 'reports'),
            ('judge_dashboard', [], 'judge_dashboard'),
            ('judge_profile', [], 'judge_profile'),
            ('judge_history', [], 'judge_history'),
        ]
        for name, args, expected in routes:
            with self.subTest(route=name):
                path = reverse(name, args=args)
                request = RequestFactory().get(path, {'category': 'sports'})
                request.user = AnonymousUser()
                request.resolver_match = resolve(path)
                self.assertEqual(active_nav(request)['active_nav'], expected)

    def test_unresolved_request_has_no_active_navigation(self):
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        request.resolver_match = None
        self.assertIsNone(active_nav(request)['active_nav'])


class CurrentNavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('aria-current') == 'page':
            self.current_links.append(attrs.get('href'))


class NavigationRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('nav-admin', 'nav@example.com', None)
        now = timezone.now()
        cls.competition = Competition.objects.create(
            name='Navigation Cup', description='Navigation page fixture',
            status='ACTIVE', start_date=now, end_date=now + timedelta(days=1),
            created_by=cls.admin,
        )
        cls.viewer = User.objects.create_user('nav-viewer')
        cls.judge_user = User.objects.create_user('nav-judge')
        UserProfile.objects.filter(user=cls.judge_user).update(role=UserProfile.Role.JUDGE)
        Judge.objects.create(user=cls.judge_user, phone='123', status='ACTIVE')

    def assert_current_link(self, response, expected_route):
        self.assertEqual(response.status_code, 200)
        parser = CurrentNavigationParser()
        parser.feed(response.content.decode())
        self.assertEqual(parser.current_links, [reverse(expected_route)])

    def test_management_results_tally_and_reports_have_one_active_link(self):
        self.client.force_login(self.admin)
        routes = [
            ('results_list', [], 'results_list'),
            ('competition_results_detail', [self.competition.pk], 'results_list'),
            ('overall_medal_tally', [], 'overall_medal_tally'),
            ('medal_tally', [self.competition.pk], 'overall_medal_tally'),
            ('reports_home', [], 'reports_home'),
        ]
        for name, args, selected in routes:
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=args))
                self.assert_current_link(response, selected)

    def test_filtered_tally_keeps_selection_and_filtered_export(self):
        self.client.force_login(self.admin)
        for category in ('sports', 'cultural'):
            with self.subTest(category=category):
                response = self.client.get(reverse('overall_medal_tally'), {'category': category})
                self.assert_current_link(response, 'overall_medal_tally')
                self.assertContains(response, f'{reverse("export_medal_tally_csv")}?category={category}')
                self.assertContains(response, 'Clear filter')

    def test_viewer_results_navigation_and_empty_state(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('results_list'))
        self.assert_current_link(response, 'results_list')
        self.assertContains(response, 'No Results Available')
        self.assertNotContains(response, 'id="view-grid-btn"')
        self.assertNotContains(response, 'id="view-table-btn"')

    def test_judge_profile_and_history_select_their_own_links(self):
        self.client.force_login(self.judge_user)
        for name in ('judge_dashboard', 'judge_profile', 'judge_history'):
            with self.subTest(route=name):
                self.assert_current_link(self.client.get(reverse(name)), name)

    def test_records_pages_share_visual_components(self):
        self.client.force_login(self.admin)
        for name, args in (
            ('results_list', []), ('overall_medal_tally', []),
            ('medal_tally', [self.competition.pk]), ('reports_home', []),
        ):
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=args))
                self.assertContains(response, 'records-page')
                self.assertContains(response, 'records-hero')
                self.assertContains(response, 'records-panel')

    def test_results_preserve_view_controls_and_pagination(self):
        self.client.force_login(self.admin)
        now = timezone.now()
        for index in range(9):
            Competition.objects.create(
                name=f'Competition {index}', description='Pagination fixture',
                start_date=now, end_date=now + timedelta(days=1), created_by=self.admin,
            )
        response = self.client.get(reverse('results_list'))
        self.assertContains(response, '10 competitions')
        for element_id in ('view-grid-btn', 'view-table-btn', 'grid-view', 'table-view'):
            self.assertContains(response, f'id="{element_id}"')
        response = self.client.get(reverse('results_list'), {'page': 2})
        self.assert_current_link(response, 'results_list')
        self.assertEqual(len(response.context['competition_results']), 1)
        self.assertContains(response, '10 competitions')


class TeamManagerDashboardTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from teams.models import Team, TeamStaff, TeamMembership
        from participants.models import Participant
        from registrations.models import EventRegistration
        cls.owner=User.objects.create_superuser('dash-owner','','pass')
        cls.manager=User.objects.create_user('dash-manager',password='pass')
        cls.manager.account_profile.role=UserProfile.Role.TEAM_MANAGER
        cls.manager.account_profile.save()
        cls.team=Team.objects.create(name='Managed delegation',category='SPORTS',status='APPROVED',created_by=cls.owner)
        cls.other=Team.objects.create(name='Private delegation',category='SPORTS',status='APPROVED',created_by=cls.owner)
        TeamStaff.objects.create(team=cls.team,user=cls.manager,role='MANAGER')
        TeamStaff.objects.create(team=cls.team,user=cls.manager,role='COACH')
        cls.competition=Competition.objects.create(name='Manager meet',description='Meet',start_date='2026-12-01T08:00:00Z',end_date='2026-12-05T17:00:00Z',status='ACTIVE',created_by=cls.owner)
        cls.player=Participant.objects.create(name='Dashboard player',phone='0')
        TeamMembership.objects.create(team=cls.team,participant=cls.player)
        cls.registration=EventRegistration.objects.create(registrant=cls.owner,team=cls.team,competition=cls.competition,status='UNDER_REVIEW')
        cls.foreign=EventRegistration.objects.create(registrant=cls.manager,team=cls.other,competition=cls.competition,status='APPROVED')

    def setUp(self):
        self.client.force_login(self.manager)

    def test_dashboard_counts_and_team_registration_visibility(self):
        response=self.client.get(reverse('team_manager_dashboard'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['team_count'],1)
        self.assertEqual(response.context['player_count'],1)
        self.assertEqual(response.context['registration_counts'],{'total':1,'pending':1,'approved':0,'rejected':0})
        self.assertContains(response,self.team.name)
        self.assertNotContains(response,self.other.name)
        self.assertEqual([r.pk for r in response.context['recent_registrations']],[self.registration.pk])
        self.assertContains(response,reverse('team_detail',args=[self.team.pk])+'#team-roster')

    def test_login_and_portal_show_manager_dashboard(self):
        self.client.logout()
        response=self.client.post(reverse('login'),{'username':'dash-manager','password':'pass'})
        self.assertRedirects(response,reverse('team_manager_dashboard'))
        self.assertTemplateUsed(self.client.get(reverse('portal_home')),'accounts/team_manager_dashboard.html')

    def test_registrations_include_other_submitters_and_reject_foreign_filters(self):
        response=self.client.get(reverse('my_registrations'))
        self.assertEqual([r.pk for r in response.context['registrations']],[self.registration.pk])
        self.assertContains(response,'Submitted by dash-owner')
        self.assertContains(response,'Team Registrations')
        response=self.client.get(reverse('my_registrations'),{'team':self.other.pk})
        self.assertEqual(len(response.context['registrations']),0)
        response=self.client.get(reverse('my_registrations'),{'status':'awaiting'})
        self.assertEqual(len(response.context['registrations']),1)

    def test_revoked_team_assignment_removes_access(self):
        from teams.models import TeamStaff
        TeamStaff.objects.filter(team=self.team,user=self.manager).delete()
        response=self.client.get(reverse('team_manager_dashboard'))
        self.assertEqual(response.context['team_count'],0)
        self.assertEqual(response.context['registration_counts']['total'],0)
        self.assertEqual(len(self.client.get(reverse('my_registrations')).context['registrations']),0)

    def test_role_protection_and_team_preselection(self):
        response=self.client.get(reverse('register_for_event'),{'team':self.team.pk})
        self.assertEqual(response.context['form'].initial['team'],self.team.pk)
        response=self.client.get(reverse('register_for_event'),{'team':self.other.pk})
        self.assertNotIn('team',response.context['form'].initial)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('team_manager_dashboard')).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('team_manager_dashboard')).status_code,302)

    def test_participant_registration_visibility_remains_personal(self):
        from registrations.models import EventRegistration
        participant=User.objects.create_user('dashboard-participant',password='pass')
        participant.account_profile.role=UserProfile.Role.PARTICIPANT
        participant.account_profile.save()
        personal=EventRegistration.objects.create(registrant=participant,participant=self.player,competition=self.competition)
        self.client.force_login(participant)
        response=self.client.get(reverse('my_registrations'))
        self.assertEqual([r.pk for r in response.context['registrations']],[personal.pk])

    def test_upcoming_matches_are_scoped_and_not_duplicated_by_staff_roles(self):
        from sports.models import SportType, SportsEvent, Match, MatchEntry
        sport=SportType.objects.create(name='Dashboard basketball')
        event=SportsEvent.objects.create(name='Dashboard event',sport_type=sport,competition=self.competition)
        upcoming=Match.objects.create(event=event,scheduled_start=timezone.now()+timedelta(days=1))
        private=Match.objects.create(event=event,scheduled_start=timezone.now()+timedelta(days=1))
        MatchEntry.objects.create(match=upcoming,team=self.team,side=1)
        MatchEntry.objects.create(match=private,team=self.other,side=1)
        response=self.client.get(reverse('team_manager_dashboard'))
        self.assertEqual([match.pk for match in response.context['upcoming_matches']],[upcoming.pk])

    def test_duplicate_team_registration_returns_validation_error(self):
        from sports.models import SportType, SportsEvent
        from registrations.models import EventRegistration
        sport=SportType.objects.create(name='Registration basketball')
        event=SportsEvent.objects.create(name='Registration event',sport_type=sport,competition=self.competition)
        EventRegistration.objects.create(registrant=self.owner,team=self.team,sport_event=event,competition=self.competition)
        response=self.client.post(reverse('register_for_event'), {'target_type':'sport_event','sport_event':event.pk,'team':self.team.pk})
        self.assertEqual(response.status_code,200)
        self.assertIn('team',response.context['form'].errors)
        self.assertEqual(EventRegistration.objects.filter(team=self.team,sport_event=event).count(),1)
