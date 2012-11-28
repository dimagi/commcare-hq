import json
from corehq.apps.users.forms import RoleForm
from django import forms
from django.contrib.auth.models import User

from corehq.apps.registration.forms import NewWebUserRegistrationForm # Reuse to capture new user info


########################################################################################################
#
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

########################################################################################################


class AdminInvitesUserForm(RoleForm, _BaseForm, forms.Form):
    from corehq.apps.users.models import OldRoles
    # As above. Need email now; still don't need domain. Don't need TOS. Do need the is_active flag,
    # and do need to relabel some things.
    email       =  forms.EmailField(label="Email Address",
                                    max_length=User._meta.get_field('email').max_length)
#    is_domain_admin = forms.BooleanField(label='User is a domain administrator', initial=False, required=False)
    role = forms.ChoiceField(choices=(), label="Project Role")

    def __init__(self, data=None, excluded_emails=None, *args, **kwargs):
        super(AdminInvitesUserForm, self).__init__(data=data, *args, **kwargs)
        self.excluded_emails = excluded_emails or []

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if email in self.excluded_emails:
            raise forms.ValidationError("A user with this email address is already on this project.")
        return email

    
class AdminRegistersUserForm(NewWebUserRegistrationForm):
    # As above. Need email now; still don't need domain. Don't need TOS. Do need the is_active flag,
    # and do need to relabel some things.
    is_domain_admin = forms.BooleanField(label='User is a domain administrator', initial=False, required=False)
           
    def __init__(self, *args, **kwargs):
        # Value of 'kind' is irrelevant in this context
        super(AdminRegistersUserForm, self).__init__(None, *args, **kwargs)
        del self.fields['domain_name']    
        del self.fields['tos_confirmed']
        self.fields['first_name'].label = 'User first name'
        self.fields['last_name'].label = 'User last (family) name'
        self.fields['email'].label = 'User email address'

########################################################################################################