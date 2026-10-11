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


class RegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150)
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
        fields = ('full_name', 'username', 'email', 'phone', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
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
        names = self.cleaned_data['full_name'].strip().split(maxsplit=1)
        user.first_name = names[0]
        user.last_name = names[1] if len(names) > 1 else ''
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data['role']
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
    full_name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    profile_image = forms.ImageField(required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        self.profile = profile
        kwargs.setdefault('initial', {
            'full_name': user.get_full_name(),
            'username': user.username,
            'email': user.email,
            'phone': profile.phone,
        })
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
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
        names = self.cleaned_data['full_name'].strip().split(maxsplit=1)
        self.user.first_name = names[0]
        self.user.last_name = names[1] if len(names) > 1 else ''
        self.user.username = self.cleaned_data['username']
        self.user.email = self.cleaned_data['email']
        self.user.save()

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
