from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.core.validators import EmailValidator, email_re
from django.forms.widgets import PasswordInput, HiddenInput
from django.utils.encoding import smart_str
from django.utils.translation import ugettext_lazy as _
from dimagi.utils.timezones.fields import TimeZoneField
from dimagi.utils.timezones.forms import TimeZoneChoiceField
from corehq.apps.users.models import CouchUser, WebUser, OldRoles, DomainMembership
from corehq.apps.users.util import format_username

class ProjectSettingsForm(forms.Form):
    """
    Form for updating a user's project settings
    """
    global_timezone = forms.CharField(initial="UTC", widget=forms.HiddenInput())
    user_timezone = TimeZoneChoiceField(label="My Timezone", initial=global_timezone.initial, widget=forms.Select(attrs={'class': 'input-xlarge'}))

    def clean_user_timezone(self):
        data = self.cleaned_data['user_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def save(self, web_user, domain):
        try:
            web_user.get_domain_membership(domain).timezone = self.cleaned_data['user_timezone']
            web_user.save()
            return True
        except Exception as e:
            return False

class RoleForm(forms.Form):

    def __init__(self, *args, **kwargs):
        if kwargs.has_key('role_choices'):
            role_choices = kwargs.pop('role_choices')
        else:
            role_choices = ()
        super(RoleForm, self).__init__(*args, **kwargs)
        self.fields['role'].choices = role_choices

class UserForm(RoleForm):
    """
    Form for Users
    """

    #username = forms.CharField(max_length=15)
    first_name = forms.CharField(max_length=50, required=False)
    last_name = forms.CharField(max_length=50, required=False)
    email = forms.EmailField(label=_("E-mail"), max_length=75, required=False)
    role = forms.ChoiceField(choices=(), required=False)

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
            validate_username('%s@commcarehq.org' % username)
            domain = self.cleaned_data['domain']
            username = format_username(username, domain)
            num_couch_users = len(CouchUser.view("users/by_username",
                                                 key=username))
            if num_couch_users > 0:
                raise forms.ValidationError("CommCare user already exists")

            # set the cleaned username to user@domain.commcarehq.org
            self.cleaned_data['username'] = username
        return self.cleaned_data

validate_username = EmailValidator(email_re, _(u'Username contains invalid characters.'), 'invalid')


