from django import forms

from participants.models import Participant
from teams.models import Team

from .models import Award, AwardRecipient


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)


class AwardForm(forms.ModelForm):
    class Meta:
        model = Award
        fields = ('name', 'type', 'description', 'rank', 'is_active')
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rank'].required = False
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = INPUT_CLASS.replace('h-12', 'min-h-24')
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500'
            else:
                field.widget.attrs['class'] = INPUT_CLASS


class AwardRecipientForm(forms.Form):
    recipient_type = forms.ChoiceField(choices=AwardRecipient.RecipientType.choices)
    participant = forms.ModelChoiceField(queryset=Participant.objects.none(), required=False)
    team = forms.ModelChoiceField(queryset=Team.objects.none(), required=False)
    citation = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)

    def __init__(self, *args, award, **kwargs):
        super().__init__(*args, **kwargs)
        self.award = award
        if award.pk:
            taken_participant_ids = award.recipients.exclude(participant__isnull=True).values_list('participant_id', flat=True)
            taken_team_ids = award.recipients.exclude(team__isnull=True).values_list('team_id', flat=True)
        else:
            taken_participant_ids = []
            taken_team_ids = []
        self.fields['participant'].queryset = Participant.objects.filter(
            status='ACTIVE',
        ).exclude(id__in=taken_participant_ids).order_by('name')
        self.fields['team'].queryset = Team.objects.filter(
            status=Team.Status.APPROVED,
        ).exclude(id__in=taken_team_ids).order_by('name')
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = INPUT_CLASS.replace('h-12', 'min-h-20')
            else:
                field.widget.attrs['class'] = INPUT_CLASS

    def clean(self):
        cleaned = super().clean()
        recipient_type = cleaned.get('recipient_type')
        if recipient_type == AwardRecipient.RecipientType.TEAM:
            if not cleaned.get('team'):
                self.add_error('team', 'Select a team to receive this award.')
            cleaned['participant'] = None
        else:
            if not cleaned.get('participant'):
                self.add_error('participant', 'Select a participant to receive this award.')
            cleaned['team'] = None
        return cleaned
