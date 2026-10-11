from django import forms
from django.contrib.auth.models import User

from accounts.models import UserProfile
from participants.models import Participant
from .models import Team, TeamMembership, TeamStaff


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ('name', 'category', 'description', 'logo', 'status')
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, allow_status=True, force_approved=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.force_approved = force_approved
        # Competition management approves a team the moment it creates one, so
        # the status is fixed rather than offered as a choice. Team managers
        # still submit for approval, and editors keep the ability to suspend.
        if force_approved or not allow_status:
            self.fields.pop('status')
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS

    def save(self, commit=True):
        team = super().save(commit=False)
        if self.force_approved:
            team.status = Team.Status.APPROVED
        if commit:
            team.save()
            self.save_m2m()
        return team


class TeamStaffForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none())
    role = forms.ChoiceField(choices=TeamStaff.Role.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.filter(
            account_profile__role=UserProfile.Role.TEAM_MANAGER,
            is_active=True,
        ).order_by('first_name', 'last_name', 'username')
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS


class TeamMembershipForm(forms.ModelForm):
    participant = forms.ModelChoiceField(queryset=Participant.objects.none())

    class Meta:
        model = TeamMembership
        fields = ('participant', 'member_number')

    def __init__(self, *args, team, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['participant'].queryset = Participant.objects.filter(
            team_membership__isnull=True,
            status='ACTIVE',
        ).order_by('name')
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS

    def clean_member_number(self):
        member_number = self.cleaned_data.get('member_number')
        if member_number is not None and member_number > 999:
            raise forms.ValidationError('Member number must be between 1 and 999.')
        return member_number
