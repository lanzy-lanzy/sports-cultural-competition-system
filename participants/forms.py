from pathlib import Path

from django import forms

from .models import Participant


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = (
            'name', 'email', 'phone', 'birth_date', 'age', 'gender', 'category',
            'team_name', 'bio', 'achievements', 'status', 'profile_image',
            'identification_type', 'identification_number', 'identification_document',
        )
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
            'achievements': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, self_service=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.self_service = self_service
        if self_service:
            self.fields.pop('status')
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS

    def clean_identification_document(self):
        document = self.cleaned_data.get('identification_document')
        if not document:
            return document
        if document.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Identification documents must be 5 MB or smaller.')
        allowed = {'.pdf', '.jpg', '.jpeg', '.png'}
        if Path(document.name).suffix.lower() not in allowed:
            raise forms.ValidationError('Upload a PDF, JPG, JPEG, or PNG document.')
        return document

    def clean(self):
        cleaned_data = super().clean()
        identification_type = cleaned_data.get('identification_type')
        identification_document = cleaned_data.get('identification_document')
        if identification_document and not identification_type:
            self.add_error('identification_type', 'Select the type of identification uploaded.')
        return cleaned_data
