from corehq.apps.commtrack.models import Program
from corehq.apps.users.models import CouchUser
from django import forms
from django.contrib.auth.models import User
from corehq.apps.users.forms import RoleForm, SupplyPointSelectWidget
import re
from corehq.apps.domain.forms import clean_password, max_pwd
from django.core.validators import validate_email
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import new_domain_re, new_org_re, website_re
from corehq.apps.orgs.models import Organization
from django.utils.encoding import smart_str
from django.utils.safestring import mark_safe
from dimagi.utils.timezones.fields import TimeZoneField
from dimagi.utils.timezones.forms import TimeZoneChoiceField
from django.utils.translation import ugettext_lazy as _

class NewWebUserRegistrationForm(forms.Form):
    """
    Form for a brand new user, before they've created a domain or done anything on CommCare HQ.
    """
    full_name = forms.CharField(label=_('Full Name'),
                                max_length=User._meta.get_field('first_name').max_length +
                                           User._meta.get_field('last_name').max_length + 1)
    email = forms.EmailField(label=_('Email Address'),
                             max_length=User._meta.get_field('email').max_length,
                             help_text=_('You will use this email to log in.'))
    password = forms.CharField(label=_('Create Password'),
                               max_length=max_pwd,
                               widget=forms.PasswordInput(render_value=False))
    email_opt_in = forms.BooleanField(required=False,
                                      initial=True,
                                      label="",
                                      help_text=_("Opt into emails about new features and other CommCare updates."))
    # Must be set to False to have the clean_*() routine called
    eula_confirmed = forms.BooleanField(required=False,
                                        label="",
                                        help_text=mark_safe(_(
                                            """I have read and agree to the
                                               <a data-toggle='modal'
                                                  data-target='#eulaModal'
                                                  href='#eulaModal'>
                                                  CommCare HQ End User License Agreement
                                               </a>.""")))
    # not required for when a user accepts an invitation
    domain_type = forms.CharField(
        required=False, widget=forms.HiddenInput(), initial='commcare')

    def clean_full_name(self):
        data = self.cleaned_data['full_name'].split()
        return [data.pop(0)] + [' '.join(data)]

    def clean_email(self):
        data = self.cleaned_data['email'].strip().lower()
        validate_email(data)
        duplicate = CouchUser.get_by_username(data)
        if duplicate:
            # sync django user
            duplicate.save()
        if User.objects.filter(username__iexact=data).count() > 0 or duplicate:
            raise forms.ValidationError('Username already taken; please try another')
        return data

    def clean_password(self):
        return clean_password(self.cleaned_data.get('password'))

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data

    def clean_eula_confirmed(self):
        data = self.cleaned_data['eula_confirmed']
        if data is not True:
            raise forms.ValidationError('You must agree to our End User License Agreement in order to register an account.')
        return data


class OrganizationRegistrationForm(forms.Form):
    """
    form for creating an organization for the first time
    """

    org_title = forms.CharField(label='Organization Title:', max_length=25, help_text='e.g. - Dimagi Inc')
    org_name = forms.CharField(label='Organization ID:', max_length=25, help_text='e.g. - dimagi')
    email = forms.CharField(label='Organization Email:', max_length=35, required=False)
    url = forms.CharField(label='Organization Homepage:', max_length=35, required=False)
    location = forms.CharField(label='Organization Location:', max_length=25, required=False)
    # logo = forms.ImageField(label='Organization Logo:', required=False)

    def clean_org_name(self):
        data = self.cleaned_data['org_name'].strip().lower()
        if not re.match("^%s$" % new_org_re, data):
            raise forms.ValidationError('Only lowercase letters and numbers allowed. Single hyphens may be used to separate words.')
        if Organization.get_by_name(data) or Organization.get_by_name(data.replace('-', '.')):
            raise forms.ValidationError('Organization name already taken---please try another')
        return data

    def clean_org_title(self):
        data = self.cleaned_data['org_title'].strip()
        return data

    def clean_email(self):
        data = self.cleaned_data['email'].strip()
        if not data == '':
            validate_email(data)
        return data

    def clean_url(self):
        data = self.cleaned_data['url'].strip()
        if not re.match("^%s$" % website_re, data) and not data == '':
            raise forms.ValidationError('invalid url')
        return data

    def clean_location(self):
        data = self.cleaned_data['location']
        return data

    # def clean_logo(self):
    #     data = self.cleaned_data['logo']
    #     #resize image to fit in website nicely
    #     return data

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data

class DomainRegistrationForm(forms.Form):
    """
    Form for creating a domain for the first time
    """
    org = forms.CharField(widget=forms.HiddenInput(), required=False)
    domain_name = forms.CharField(label=_('Project Name:'), max_length=25,
                                  help_text=_("Project name cannot contain spaces."))
    domain_type = forms.CharField(widget=forms.HiddenInput(), required=False,
                                  initial='commcare')
    domain_timezone = TimeZoneChoiceField(
        label=_("Time Zone:"), initial="UTC", required=False,
        widget=forms.Select(attrs={'class': 'input-xlarge',
                                   'bindparent': 'visible: override_tz',
                                   'data-bind': 'event: {change: updateForm}'}))

    def clean_domain_name(self):
        data = self.cleaned_data['domain_name'].strip().lower()
        if not re.match("^%s$" % new_domain_re, data):
            raise forms.ValidationError('Only lowercase letters and numbers allowed. Single hyphens may be used to separate words.')

        conflict = Domain.get_by_name(data) or Domain.get_by_name(data.replace('-', '.'))
        if conflict:
            raise forms.ValidationError('Project name already taken---please try another')
        return data

    def clean_domain_type(self):
        data = self.cleaned_data.get('domain_type', '').strip().lower()
        return data if data else 'commcare'

    def clean_domain_timezone(self):
        data = self.cleaned_data['domain_timezone']
        timezone_field = TimeZoneField()
        timezone_field.run_validators(data)
        return smart_str(data)

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data

# From http://www.peterbe.com/plog/automatically-strip-whitespace-in-django-app_manager
#
# I'll put this in each app, so they can be standalone, but it should really go in some centralized 
# part of the distro

class _BaseForm(object):
    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data


class AdminInvitesUserForm(RoleForm, _BaseForm, forms.Form):
    # As above. Need email now; still don't need domain. Don't need TOS. Do need the is_active flag,
    # and do need to relabel some things.
    email       =  forms.EmailField(label="Email Address",
                                    max_length=User._meta.get_field('email').max_length)
#    is_domain_admin = forms.BooleanField(label='User is a domain administrator', initial=False, required=False)
    role = forms.ChoiceField(choices=(), label="Project Role")

    def __init__(self, data=None, excluded_emails=None, *args, **kwargs):
        domain = None
        if 'domain' in kwargs:
            domain = Domain.get_by_name(kwargs['domain'])
            del kwargs['domain']
        super(AdminInvitesUserForm, self).__init__(data=data, *args, **kwargs)
        if domain and domain.commtrack_enabled:
            self.fields['supply_point'] = forms.CharField(label='Supply Point:', required=False, widget=SupplyPointSelectWidget(domain=domain.name))
            self.fields['program'] = forms.ChoiceField(label="Program", choices=(), required=False)
            programs = Program.by_domain(domain.name, wrap=False)
            choices = list((prog['_id'], prog['name']) for prog in programs)
            choices.insert(0, ('', ''))
            self.fields['program'].choices = choices
        self.excluded_emails = excluded_emails or []

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if email in self.excluded_emails:
            raise forms.ValidationError(_("A user with this email address is already in "
                                          "this project or has a pending invitation."))
        return email

