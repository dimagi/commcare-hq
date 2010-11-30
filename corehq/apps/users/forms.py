from django import forms
from corehq.apps.users.models import CouchUser
from django.forms.models import ModelMultipleChoiceField, ModelChoiceField
from django.forms.widgets import PasswordInput, RadioSelect
from django.forms.fields import ChoiceField
from django.utils.translation import ugettext_lazy as _

class UserForm(forms.Form):
    """
    Form for Users
    """
    username = forms.CharField(max_length=15)
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    # TODO: move this to another form
    # password = forms.CharField(widget=PasswordInput())
    # password_2 = forms.CharField(widget=PasswordInput())
    email = forms.EmailField(label=_("E-mail"), max_length=75)
    # TODO: add phone_numbers
    # TODO: add associated commcare users
    
    class Meta:
        app_label = 'users'