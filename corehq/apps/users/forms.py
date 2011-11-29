from django import forms
from django.core.validators import EmailValidator, email_re
from django.forms.widgets import PasswordInput, HiddenInput
from django.utils.translation import ugettext_lazy as _
from corehq.apps.users.models import CouchUser, WebUser
from corehq.apps.users.util import format_username

class UserForm(forms.Form):
    """
    Form for Users
    """
    #username = forms.CharField(max_length=15)
    first_name = forms.CharField(max_length=50, required=False)
    last_name = forms.CharField(max_length=50, required=False)
    email = forms.EmailField(label=_("E-mail"), max_length=75, required=False)
    role = forms.ChoiceField(choices=WebUser.ROLE_LABELS, required=False)
    
    class Meta:
        app_label = 'users'

class CommCareAccountForm(forms.Form):
    """
    Form for CommCareAccounts
    """
    username = forms.CharField(max_length=15)
    password = forms.CharField(widget=PasswordInput())
    password_2 = forms.CharField(label='Password (reenter)', widget=PasswordInput())
    domain = forms.CharField(widget=HiddenInput())
    
    class Meta:
        app_label = 'users'
    
    def clean(self):
        try:
            password = self.cleaned_data['password']
            password_2 = self.cleaned_data['password_2']
        except KeyError:
            pass
        else:
            if password != password_2:
                raise forms.ValidationError("Passwords do not match")

        try:
            username = self.cleaned_data['username']
        except KeyError:
            pass
        else:
            validate_user('%s@commcarehq.org' % username)
            domain = self.cleaned_data['domain']
            username = format_username(username, domain)
            num_couch_users = len(CouchUser.view("users/by_username",
                                                 key=username))
            if num_couch_users > 0:
                raise forms.ValidationError("CommCare user already exists")

            # set the cleaned username to user@domain.commcarehq.org
            self.cleaned_data['username'] = username
        return self.cleaned_data

validate_user = EmailValidator(email_re, _(u'Username contains invalid characters.'), 'invalid')
