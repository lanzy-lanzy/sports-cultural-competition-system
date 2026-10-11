from pathlib import Path

from django import forms

from competitions.models import Competition
from .models import EligibilityRecord


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)


class EligibilitySubmissionForm(forms.ModelForm):
    class Meta:
        model = EligibilityRecord
        fields = ('competition', 'document', 'notes')
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, participant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.participant = participant
        queryset = Competition.objects.filter(status='ACTIVE')
        if participant is not None:
            taken = participant.eligibility_records.values_list('competition_id', flat=True)
            queryset = queryset.exclude(id__in=taken)
        self.fields['competition'].queryset = queryset
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = INPUT_CLASS.replace('h-12', 'min-h-24')
            else:
                field.widget.attrs['class'] = INPUT_CLASS

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if not document:
            return document
        if document.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Eligibility documents must be 5 MB or smaller.')
        allowed = {'.pdf', '.jpg', '.jpeg', '.png'}
        if Path(document.name).suffix.lower() not in allowed:
            raise forms.ValidationError('Upload a PDF, JPG, JPEG, or PNG document.')
        return document
