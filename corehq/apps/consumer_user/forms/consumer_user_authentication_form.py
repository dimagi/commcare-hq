from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _


from corehq.apps.domain.forms import NoAutocompleteMixin


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

        cleaned_data = super(ConsumerUserAuthenticationForm, self).clean()

        if self.invitation and not self.invitation.accepted:
            self.invitation.accept_for_django_user(self.user_cache)

        return cleaned_data
