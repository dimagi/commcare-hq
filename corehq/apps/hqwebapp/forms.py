from corehq.apps.users.models import CouchUser
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label=_("E-mail"), max_length=75)

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        return username

class CloudCareAuthenticationForm(EmailAuthenticationForm):
    username = forms.EmailField(label=_("Username"), max_length=75)
