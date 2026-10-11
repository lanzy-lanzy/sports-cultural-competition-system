from pathlib import Path

from django import forms

from competitions.models import Competition
from sports.models import Match, SportsEvent

from .models import Protest


class ProtestForm(forms.Form):
    target_type = forms.ChoiceField(
        choices=(
            ('competition', 'Competition'),
            ('sport_event', 'Sport event'),
            ('match', 'Match'),
        ),
        initial='match',
    )
    competition = forms.ModelChoiceField(queryset=Competition.objects.none(), required=False)
    sport_event = forms.ModelChoiceField(queryset=SportsEvent.objects.none(), required=False)
    match = forms.ModelChoiceField(queryset=Match.objects.none(), required=False)
    title = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}))
    supporting_document = forms.FileField(required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['competition'].queryset = Competition.objects.all().order_by('-id')
        self.fields['sport_event'].queryset = SportsEvent.objects.select_related('sport_type').order_by('name')
        self.fields['match'].queryset = Match.objects.select_related('event', 'event__sport_type').order_by('-scheduled_start', 'id')
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'min-h-32 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 text-sm text-slate-800 outline-none transition focus:border-campus focus:bg-white focus:ring-4 focus:ring-teal-100'
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = (
                    'block w-full text-sm text-slate-500 file:mr-4 file:rounded-lg file:border-0 '
                    'file:bg-cyan-50 file:px-4 file:py-2 file:text-sm file:font-semibold '
                    'file:text-cyan-700 hover:file:bg-cyan-100'
                )
            else:
                field.widget.attrs['class'] = (
                    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
                    'text-sm text-slate-800 outline-none transition focus:border-campus '
                    'focus:bg-white focus:ring-4 focus:ring-teal-100'
                )

    def clean_supporting_document(self):
        document = self.cleaned_data.get('supporting_document')
        if not document:
            return document
        if document.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Supporting documents must be 5 MB or smaller.')
        allowed = {'.pdf', '.jpg', '.jpeg', '.png'}
        if Path(document.name).suffix.lower() not in allowed:
            raise forms.ValidationError('Upload a PDF, JPG, JPEG, or PNG document.')
        return document

    def clean(self):
        cleaned = super().clean()
        target_type = cleaned.get('target_type')
        if target_type == 'match':
            if not cleaned.get('match'):
                self.add_error('match', 'Select the match being protested.')
            cleaned['competition'] = None
            cleaned['sport_event'] = None
        elif target_type == 'sport_event':
            if not cleaned.get('sport_event'):
                self.add_error('sport_event', 'Select the sport event.')
            cleaned['competition'] = None
            cleaned['match'] = None
        else:
            if not cleaned.get('competition'):
                self.add_error('competition', 'Select the competition.')
            cleaned['sport_event'] = None
            cleaned['match'] = None
        return cleaned