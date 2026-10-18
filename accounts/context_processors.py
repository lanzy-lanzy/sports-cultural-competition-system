NAV_GROUPS = {
    'dashboard': ['dashboard'],
    'portal': ['portal_home'],
    'users': ['user_management', 'update_user_access'],
    'judge_dashboard': ['judge_dashboard', 'judge_profile', 'judge_history'],
    'competitions': [
        'competition_list', 'create_competition', 'competition_detail',
        'edit_competition', 'delete_competition', 'toggle_competition_status',
        'manage_rounds', 'create_round', 'edit_round', 'delete_round',
        'toggle_round_status', 'start_round', 'complete_round',
    ],
    'participants': [
        'participant_list', 'participant_detail', 'delete_participant',
        'create_participant', 'participant_management', 'manage_participants',
        'assign_participants', 'remove_participant_from_competition',
        'my_participant_profile',
    ],
    'teams': [
        'team_list', 'create_team', 'team_detail', 'edit_team',
        'add_team_member', 'remove_team_member', 'add_team_staff',
        'remove_team_staff', 'update_team_status',
    ],
    'judges': [
        'judge_management', 'manage_judges', 'assign_judges',
        'edit_judge_assignment', 'delete_judge_assignment',
    ],
    'sports': [
        'sports_hub',
        'sport_type_list', 'sport_type_create', 'sport_type_edit',
        'venue_list', 'venue_create', 'venue_edit', 'venue_detail',
        'competition_sport_events', 'create_sport_event',
        'sport_event_detail', 'edit_sport_event',
        'add_event_entry', 'update_entry_status', 'remove_event_entry',
        'generate_event_bracket', 'clear_event_bracket',
        'match_schedule', 'edit_match', 'record_match_result',
        'event_standings', 'event_bracket',
    ],
    'match_board': ['match_board'],
    'results': [
        'results_list', 'competition_results_detail', 'results_reveal',
        'toggle_results_visibility', 'round_results', 'generate_pdf_results',
        'scoring_panel', 'update_score', 'overall_medal_tally',
    ],
    'eligibility': [
        'my_eligibility', 'eligibility_list', 'eligibility_review',
    ],
    'announcements': [
        'announcement_list', 'create_announcement', 'edit_announcement',
        'toggle_announcement_publish', 'delete_announcement',
        'announcement_public',
    ],
    'notifications': [
        'notification_list', 'mark_notification_read',
        'mark_all_notifications_read',
    ],
    'registrations': [
        'registration_list', 'create_registration', 'my_registrations',
        'registration_review', 'registration_review_queue',
    ],
    'protests': [
        'submit_protest', 'my_protests', 'protest_list',
        'protest_detail', 'protest_review',
    ],
    'audit': [
        'audit_log_list', 'clear_audit_logs',
    ],
    'reports': [
        'reports_home', 'export_participants_csv', 'export_team_rosters_csv',
        'export_registrations_csv', 'export_schedule_csv', 'export_medal_tally_csv',
    ],
    'scoreboard': ['scoreboard'],
    'awards': [
        'award_list', 'create_award', 'edit_award', 'delete_award',
        'award_recipient_add', 'award_recipient_remove', 'certificate_pdf',
        'medal_tally',
        'overall_medal_tally',
    ],
}


def active_nav(request):
    url_name = request.resolver_match.url_name if request.resolver_match else None
    context = {'active_nav': None}
    for group, names in NAV_GROUPS.items():
        if url_name in names:
            context['active_nav'] = group
            break

    if request.user.is_authenticated:
        from .access import MANAGEMENT_ROLES, get_user_role
        from .models import UserProfile

        role = get_user_role(request.user)
        context.update({
            'account_role': role,
            'account_role_display': dict(UserProfile.Role.choices).get(role, 'User'),
            'can_manage': role in MANAGEMENT_ROLES,
            'is_account_admin': role == UserProfile.Role.ADMINISTRATOR,
            'unread_notifications': request.user.notifications.filter(is_read=False).count(),
        })
    return context
