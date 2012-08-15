from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.core.validators import EmailValidator, email_re
from django.forms.widgets import PasswordInput, HiddenInput
from django.utils.encoding import smart_str
from django.utils.translation import ugettext_lazy as _
from corehq.apps.hq_bootstrap.forms.widgets import BootstrapCheckboxInput, BootstrapDisabledInput
from dimagi.utils.timezones.fields import TimeZoneField
from dimagi.utils.timezones.forms import TimeZoneChoiceField
from corehq.apps.users.models import CouchUser, WebUser, OldRoles, DomainMembership
from corehq.apps.users.util import format_username
from corehq.apps.app_manager.models import validate_lang
import re

def wrapped_language_validation(value):
    try:
        validate_lang(value)
    except ValueError:
        raise forms.ValidationError("%s is not a valid language code! Please "
                                    "enter a valid two or three digit code." % value)

class LanguageField(forms.CharField):
    """
    Adds language code validation to a field
    """
    def __init__(self, *args, **kwargs):
        super(LanguageField, self).__init__(*args, **kwargs)
        self.min_length = 2
        self.max_length = 3
    
    default_error_messages = {
        'invalid': _(u'Please enter a valid two or three digit language code.'),
    }
    default_validators = [wrapped_language_validation]

class ProjectSettingsForm(forms.Form):
    """
    Form for updating a user's project settings
    """
    global_timezone = forms.CharField(initial="UTC",
        label="Project Timezone",
        widget=BootstrapDisabledInput(attrs={'class': 'input-xlarge'}))
    override_global_tz = forms.BooleanField(initial=False,
        required=False,
        label="",
        widget=BootstrapCheckboxInput(attrs={'data-bind': 'checked: override_tz, event: {change: updateForm}'},
            inline_label="Override project's timezone setting"))
    user_timezone = TimeZoneChoiceField(label="My Timezone",
        initial=global_timezone.initial,
        widget=forms.Select(attrs={'class': 'input-xlarge', 'bindparent': 'visible: override_tz',
                                   'data-bind': 'event: {change: updateForm}'}))

    def clean_user_timezone(self):
        data = self.cleaned_data['user_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def save(self, web_user, domain):
        try:
            timezone = self.cleaned_data['global_timezone']
            override = self.cleaned_data['override_global_tz']
            if override:
                timezone = self.cleaned_data['user_timezone']
            dm = web_user.get_domain_membership(domain)
            dm.timezone = timezone
            dm.override_global_tz = override
            web_user.save()
            return True
        except Exception:
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
    language = LanguageField(required=False)
    role = forms.ChoiceField(choices=(), required=False)
    
    
class Meta:
        app_label = 'users'

class CommCareAccountForm(forms.Form):
    """
    Form for CommCareAccounts
    """
    username = forms.CharField(max_length=15, required=True)
    password = forms.CharField(widget=PasswordInput(), required=True, min_length=1, help_text="Only numbers are allowed in passwords")
    password_2 = forms.CharField(label='Password (reenter)', widget=PasswordInput(), required=True, min_length=1)
    domain = forms.CharField(widget=HiddenInput())
    
    class Meta:
        app_label = 'users'

    def clean_username(self):
        username = self.cleaned_data['username']
        if username == 'admin' or username == 'demo_user':
            raise forms.ValidationError("The username %s is reserved for CommCare." % username)
        return username
    
    def clean(self):
        try:
            password = self.cleaned_data['password']
            password_2 = self.cleaned_data['password_2']
        except KeyError:
            pass
        else:
            if password != password_2:
                raise forms.ValidationError("Passwords do not match")
            if self.password_format == 'n' and not password.isnumeric():
                raise forms.ValidationError("Password is not numeric")

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


