from django.shortcuts import redirect
from django.urls import resolve
from django.contrib import messages


class ResultsVisibilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if resolve(request.path).url_name == 'results_reveal':
            competition_id = resolve(request.path).kwargs.get('competition_id')
            if competition_id:
                from .models import Competition
                competition = Competition.objects.get(id=competition_id)
                if not competition.show_results and not request.user.is_superuser:
                    messages.info(request, 'Results are not yet available.')
                    return redirect('competition_detail', competition_id=competition_id)

        return self.get_response(request)
