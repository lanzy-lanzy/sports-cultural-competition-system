from django import forms

from .models import Participant


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)

TEXTAREA_CLASS = INPUT_CLASS.replace('h-12 ', '') + ' py-3'

FILE_INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-dashed border-slate-300 bg-slate-50/70 px-3 '
    'text-sm text-slate-600 outline-none transition focus:border-campus focus:bg-white '
    'file:mr-3 file:rounded-lg file:border-0 file:bg-ink file:px-4 file:py-2 '
    'file:text-xs file:font-bold file:text-white'
)

# Competition identification is captured as a single School ID number; the type
# selector and document upload were removed because School ID is the only accepted
# form of identification in this system.
NAME_FIELD_ORDER = (
    'first_name', 'middle_name', 'last_name', 'profile_image', 'phone',
    'birth_date', 'age', 'gender', 'category', 'team_name', 'status',
    'identification_number', 'bio', 'achievements',
)


class ParticipantForm(forms.ModelForm):
    first_name = forms.CharField(label='First name', max_length=80)
    middle_name = forms.CharField(label='Middle name (optional)', max_length=80, required=False)
    last_name = forms.CharField(label='Last name', max_length=80)

    class Meta:
        model = Participant
        fields = (
            'name', 'phone', 'birth_date', 'age', 'gender', 'category',
            'team_name', 'bio', 'achievements', 'status', 'profile_image',
            'identification_number',
        )
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
            'achievements': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, self_service=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.self_service = self_service

        # The single stored name is captured through three dedicated inputs.
        stored_name = getattr(self.instance, 'name', '') or ''
        if not self.is_bound and stored_name and not self.initial.get('first_name'):
            first, middle, last = self.split_full_name(stored_name)
            self.initial.update({'first_name': first, 'middle_name': middle, 'last_name': last})
        self.fields.pop('name')

        self.fields['identification_number'].label = 'School ID number'
        self.fields['identification_number'].help_text = (
            'The number printed on the participant\u2019s School ID.'
        )

        if self_service:
            # Participants maintain identity and classification only; contact and
            # narrative fields are managed by administrators. The team is chosen
            # through the "My team" join/leave section (which keeps team_name in
            # sync with the roster membership), so the free-text box is removed
            # here to avoid two competing inputs for the same value.
            for field_name in ('status', 'bio', 'achievements', 'team_name'):
                self.fields.pop(field_name, None)

        self.order_fields(
            [name for name in NAME_FIELD_ORDER if name in self.fields]
        )

        for field in self.fields.values():
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = FILE_INPUT_CLASS
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = TEXTAREA_CLASS
            else:
                field.widget.attrs['class'] = INPUT_CLASS

    @staticmethod
    def split_full_name(name):
        parts = name.split()
        if not parts:
            return '', '', ''
        if len(parts) == 1:
            return parts[0], '', ''
        if len(parts) == 2:
            return parts[0], '', parts[1]
        return parts[0], ' '.join(parts[1:-1]), parts[-1]

    def composed_name(self):
        parts = [
            self.cleaned_data.get('first_name', ''),
            self.cleaned_data.get('middle_name', ''),
            self.cleaned_data.get('last_name', ''),
        ]
        return ' '.join(part.strip() for part in parts if part and part.strip())

    def save(self, commit=True):
        self.instance.name = self.composed_name()
        return super().save(commit=commit)
