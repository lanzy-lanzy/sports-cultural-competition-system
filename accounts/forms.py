from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .access import PUBLIC_REGISTRATION_ROLES, sync_staff_status
from .models import UserProfile


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)

FILE_INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-600 bg-white/5 px-3 text-xs '
    'text-slate-300 outline-none transition file:mr-3 file:rounded-lg file:border-0 '
    'file:bg-campus file:px-3 file:py-2 file:text-xs file:font-bold file:text-white'
)


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=100)
    middle_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30)
    role = forms.ChoiceField(
        choices=[
            choice for choice in UserProfile.Role.choices
            if choice[0] in PUBLIC_REGISTRATION_ROLES
        ],
        initial=UserProfile.Role.JUDGE,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'first_name', 'middle_name', 'last_name', 'username', 'email',
            'phone', 'role', 'password1', 'password2',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['middle_name'].label = 'Middle name (optional)'
        for field in self.fields.values():
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = FILE_INPUT_CLASS
            else:
                field.widget.attrs['class'] = INPUT_CLASS

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email address already exists.')
        return email

    def clean_role(self):
        role = self.cleaned_data['role']
        if role not in PUBLIC_REGISTRATION_ROLES:
            raise forms.ValidationError('This role can only be assigned by a system administrator.')
        return role

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name'].strip()
        user.last_name = self.cleaned_data['last_name'].strip()
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data['role']
            profile.middle_name = self.cleaned_data['middle_name'].strip()
            profile.phone = self.cleaned_data['phone'].strip()
            profile.save()

            if profile.role == UserProfile.Role.JUDGE:
                from judges.models import Judge
                Judge.objects.get_or_create(
                    user=user,
                    defaults={'phone': profile.phone, 'status': 'ACTIVE'},
                )
        return user


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    middle_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    profile_image = forms.ImageField(required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        self.profile = profile
        kwargs.setdefault('initial', {
            'first_name': user.first_name,
            'middle_name': profile.middle_name,
            'last_name': user.last_name,
            'username': user.username,
            'email': user.email,
            'phone': profile.phone,
        })
        super().__init__(*args, **kwargs)
        self.fields['middle_name'].label = 'Middle name (optional)'
        # Grouped as name pair, optional middle name, then contact details.
        self.order_fields(('first_name', 'last_name', 'middle_name', 'email', 'username', 'phone'))
        for field in self.fields.values():
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = FILE_INPUT_CLASS
            else:
                field.widget.attrs['class'] = INPUT_CLASS

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.exclude(pk=self.user.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already in use.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.exclude(pk=self.user.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError('This email address is already in use.')
        return email

    @transaction.atomic
    def save(self):
        self.user.first_name = self.cleaned_data['first_name'].strip()
        self.user.last_name = self.cleaned_data['last_name'].strip()
        self.user.username = self.cleaned_data['username']
        self.user.email = self.cleaned_data['email']
        self.user.save()

        self.profile.middle_name = self.cleaned_data['middle_name'].strip()
        self.profile.phone = self.cleaned_data['phone'].strip()
        if self.cleaned_data.get('profile_image'):
            self.profile.profile_image = self.cleaned_data['profile_image']
        self.profile.save()

        if hasattr(self.user, 'judge'):
            self.user.judge.phone = self.profile.phone
            if self.cleaned_data.get('profile_image'):
                self.user.judge.profile_image = self.cleaned_data['profile_image']
            self.user.judge.save()
        return self.user


class UserAccessForm(forms.Form):
    role = forms.ChoiceField(choices=UserProfile.Role.choices)
    is_active = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].widget.attrs['class'] = INPUT_CLASS

    def save(self, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = self.cleaned_data['role']
        profile.save(update_fields=['role', 'updated_at'])
        if profile.role == UserProfile.Role.JUDGE:
            from judges.models import Judge
            Judge.objects.get_or_create(
                user=user,
                defaults={'phone': profile.phone, 'status': 'ACTIVE'},
            )
        user.is_active = self.cleaned_data['is_active']
        user.save(update_fields=['is_active'])
        sync_staff_status(user, profile.role)
        return user
