from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.utils.translation import ugettext_lazy as _


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label=_("E-mail"), max_length=75)