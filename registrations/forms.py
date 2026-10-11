from pathlib import Path

from django import forms

from competitions.models import Competition
from sports.models import SportsEvent
from teams.models import Team

from .models import EventRegistration


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)


class EventRegistrationForm(forms.Form):
    target_type = forms.ChoiceField(
        choices=(
            ('sport_event', 'Sport event'),
            ('competition', 'Competition (cultural)'),
        ),
        initial='sport_event',
    )
    competition = forms.ModelChoiceField(queryset=Competition.objects.none(), required=False)
    sport_event = forms.ModelChoiceField(queryset=SportsEvent.objects.none(), required=False)
    team = forms.ModelChoiceField(queryset=Team.objects.none(), required=False)
    requirements_document = forms.FileField(required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['competition'].queryset = Competition.objects.filter(status='ACTIVE').order_by('-id')
        self.fields['sport_event'].queryset = SportsEvent.objects.filter(
            status__in=[SportsEvent.Status.PLANNED, SportsEvent.Status.SCHEDULED],
        ).select_related('sport_type').order_by('name')
        if user is not None:
            self.fields['team'].queryset = Team.objects.filter(
                staff_assignments__user=user,
            ).distinct().order_by('name')
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = INPUT_CLASS.replace('h-12', 'min-h-24')
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = (
                    'block w-full text-sm text-slate-500 file:mr-4 file:rounded-lg file:border-0 '
                    'file:bg-cyan-50 file:px-4 file:py-2 file:text-sm file:font-semibold '
                    'file:text-cyan-700 hover:file:bg-cyan-100'
                )
            else:
                field.widget.attrs['class'] = INPUT_CLASS

    def clean_requirements_document(self):
        document = self.cleaned_data.get('requirements_document')
        if not document:
            return document
        if document.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Requirement documents must be 5 MB or smaller.')
        allowed = {'.pdf', '.jpg', '.jpeg', '.png'}
        if Path(document.name).suffix.lower() not in allowed:
            raise forms.ValidationError('Upload a PDF, JPG, JPEG, or PNG document.')
        return document

    def clean(self):
        cleaned = super().clean()
        target_type = cleaned.get('target_type')

        if target_type == 'competition':
            if not cleaned.get('competition'):
                self.add_error('competition', 'Select a competition to register for.')
            cleaned['sport_event'] = None
        else:
            sport_event = cleaned.get('sport_event')
            if not sport_event:
                self.add_error('sport_event', 'Select a sport event to register for.')
            cleaned['competition'] = sport_event.competition if sport_event else None
        return cleaned
