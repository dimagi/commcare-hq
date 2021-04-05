from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import CharField, ModelForm, PasswordInput
from django.utils.translation import ugettext_lazy as _

from corehq.apps.consumer_user.models import ConsumerUser
from corehq.apps.domain.forms import NoAutocompleteMixin


class ChangeContactDetailsForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name']


class ConsumerUserAuthenticationForm(NoAutocompleteMixin, AuthenticationForm):
    username = forms.EmailField(label=_("Email Address"),
                                widget=forms.TextInput(attrs={'class': 'form-control'}),
                                required=True)
    password = forms.CharField(label=_("Password"),
                               widget=forms.PasswordInput(attrs={'class': 'form-control'}),
                               required=True)

    def __init__(self, *args, **kwargs):
        self.invitation = kwargs.pop('invitation', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        username = self.cleaned_data.get('username')
        if username is None:
            raise ValidationError(_('Please enter a valid email address.'))

        cleaned_data = super().clean()

        consumer_user, created = ConsumerUser.objects.get_or_create(user=self.user_cache)
        if self.invitation and not self.invitation.accepted:
            self.invitation.accept_for_consumer_user(consumer_user)

        return cleaned_data


class ConsumerUserSignUpForm(ModelForm):

    email = CharField(required=True)

    def __init__(self, *args, **kwargs):
        self.invitation = kwargs.pop('invitation', None)
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Email Address'
        for key in self.fields:
            self.fields[key].required = True

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password']
        widgets = {
            'password': PasswordInput(),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if (
            User.objects.filter(username=email).exists()
            or ConsumerUser.objects.filter(user__username=email).exists()
        ):
            raise ValidationError(_(u'Username "{username}" is already in use.'), params={"username": email})

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.username = self.cleaned_data['email']
        if commit:
            user.save()
            consumer_user = ConsumerUser.objects.create(user=user)
            if self.invitation and not self.invitation.accepted:
                self.invitation.accept_for_consumer_user(consumer_user)
        return user
