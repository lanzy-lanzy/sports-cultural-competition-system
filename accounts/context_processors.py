NAV_GROUPS = {
    'dashboard': ['dashboard'],
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
    ],
    'judges': [
        'judge_management', 'manage_judges', 'assign_judges',
        'edit_judge_assignment', 'delete_judge_assignment',
    ],
    'results': [
        'results_list', 'competition_results_detail', 'results_reveal',
        'toggle_results_visibility', 'round_results', 'generate_pdf_results',
        'scoring_panel', 'update_score',
    ],
}


def active_nav(request):
    url_name = request.resolver_match.url_name if request.resolver_match else None
    for group, names in NAV_GROUPS.items():
        if url_name in names:
            return {'active_nav': group}
    return {'active_nav': None}
