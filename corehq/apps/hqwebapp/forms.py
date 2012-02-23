from corehq.apps.users.models import CouchUser
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label=_("E-mail"), max_length=75)

#    def clean_username(self):
#        user = CouchUser.get_by_username(self.cleaned_data['username'])
#        if user and user.is_commcare_user():
#            raise ValidationError("You cannot log in as a phone user")
#        return self.cleaned_data['username']