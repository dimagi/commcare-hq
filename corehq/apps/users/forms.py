from django import forms
from django.forms.widgets import PasswordInput, HiddenInput
from django.utils.translation import ugettext_lazy as _
from corehq.apps.users.models import CouchUser

class UserForm(forms.Form):
    """
    Form for Users
    """
    username = forms.CharField(max_length=15)
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(label=_("E-mail"), max_length=75)
    
    class Meta:
        app_label = 'users'

class CommCareAccountForm(forms.Form):
    """
    Form for CommCareAccounts
    """
    username = forms.CharField(max_length=15)
    password = forms.CharField(widget=PasswordInput())
    password_2 = forms.CharField(widget=PasswordInput())
    domain = forms.CharField(widget=HiddenInput())
    
    class Meta:
        app_label = 'users'
    
    def clean(self):
        if self.cleaned_data['password'] != self.cleaned_data['password_2']:
            raise forms.ValidationError("Passwords do not match")
        username = self.cleaned_data['username']
        domain = self.cleaned_data['domain']
        num_couch_users = len(CouchUser.view("users/by_commcare_username_domain", 
                                             key=[username, domain]))
        if num_couch_users > 0:
            raise forms.ValidationError("CommCare user already exists")
        return self.cleaned_data
