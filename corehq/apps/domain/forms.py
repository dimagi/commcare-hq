import re
from django import forms
from django.contrib.auth.models import User

import django_tables as tables

from corehq.apps.domain.middleware import _SESSION_KEY_SELECTED_DOMAIN
from corehq.apps.domain.models import Domain

########################################################################################################
#
# From http://www.peterbe.com/plog/automatically-strip-whitespace-in-django-forms
#
# I'll put this in each app, so they can be standalone, but it should really go in some centralized 
# part of the distro. 
#
# Need to remember to call:
#
# super(_BaseForm, self).clean() in any derived class that overrides clean()
from corehq.apps.domain.urls import domain_re

class _BaseForm(object):
    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data

########################################################################################################

class DomainModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name

########################################################################################################

class DomainBoundModelChoiceField(forms.ModelChoiceField):
    """A model choice field for an object that is restricted by domain"""
    
    _domain = None
    
    def _get_domain(self):
        return self._domain
    
    def _set_domain(self, domain):
        _domain = domain
        self.queryset = self.queryset.model.objects.filter(domain_membership__domain=domain)
    
    domain = property(_get_domain, _set_domain)

    
########################################################################################################

class DomainSelectionForm(forms.Form):
    domain_list = DomainModelChoiceField(queryset=Domain.objects.none(),empty_label=None)

    def __init__(self, domain_list=None, *args, **kwargs):
        super(DomainSelectionForm, self).__init__(*args, **kwargs)
        # Here's how we set the runtime filtering of the domains to be displayed in the
        # selector box
        if domain_list is not None:
            self.fields['domain_list'].queryset = domain_list

    def save( self, 
              request, 
              selected_domain_key = _SESSION_KEY_SELECTED_DOMAIN ):            
        d = Domain(id = self.cleaned_data['domain_list'].id,
                   name = self.cleaned_data['domain_list'].name )
        request.session[selected_domain_key] = d
        request.user.selected_domain = d                                                          
        return True

########################################################################################################

min_pwd = 4
max_pwd = 20
pwd_pattern = re.compile( r"([-\w]){"  + str(min_pwd) + ',' + str(max_pwd) + '}' )

def clean_password(txt):
    if len(txt) < min_pwd:
        raise forms.ValidationError('Password is too short; must be at least %s characters' % min_pwd )
    if len(txt) > max_pwd:
        raise forms.ValidationError('Password is too long; must be less than %s characters' % max_pwd )
    if not pwd_pattern.match(txt):
        raise forms.ValidationError('Password may only contain letters, numbers, hyphens, and underscores')
    return txt
    
class RegistrationRequestForm(_BaseForm, forms.Form):
    first_name  =  forms.CharField(label='First Name', max_length=User._meta.get_field('first_name').max_length)
    last_name   =  forms.CharField(label='Last Name', max_length=User._meta.get_field('last_name').max_length)
    email       =  forms.EmailField(label='Email Address',
                                    max_length=User._meta.get_field('email').max_length, 
                                    help_text='You will use this to log in')
    domain_name =  forms.CharField(label='Domain Name', max_length=Domain._meta.get_field('name').max_length)
    password_1  =  forms.CharField(label='Password', max_length=max_pwd, widget=forms.PasswordInput(render_value=False))
    password_2  =  forms.CharField(label='Password (reenter)', max_length=max_pwd, widget=forms.PasswordInput(render_value=False))
    
    tos_confirmed = forms.BooleanField(required=False, label='Agree to Terms of Service') # Must be set to False to have the clean_*() routine called
        
    def __init__(self, kind="new_user", *args, **kwargs):
        super(RegistrationRequestForm, self).__init__(*args, **kwargs)
        if kind=="existing_user":
            del self.fields['first_name']
            del self.fields['last_name']
            del self.fields['email']
            del self.fields['password_1']
            del self.fields['password_2']        
        
    # Tests for unique name and domain are merely advisory at this point; because they happen before
    # the attempted object insertion, another user could sneak a clashing name in before the insert.
    # Thus, even if we pass these tests, we might fail upon insert (and will have to return an 
    # error message accordingly).
    
    def clean_domain_name(self):
        data = self.cleaned_data['domain_name'].strip().lower()
        #data = re.sub(r"[-_ ]", '.', data)
        if not re.match("^%s$" % domain_re, data):
            raise forms.ValidationError('Only lowercase letters and periods ("-") allowed in domain name')
        if Domain.objects.filter(name__iexact=data).count() > 0:
            raise forms.ValidationError('Domain name already taken; please try another')
        return data
 
    def clean_email(self):
        data = self.cleaned_data['email'].strip()
        if User.objects.filter(username__iexact=data).count() > 0:
            raise forms.ValidationError('Username already taken; please try another')
        return data
 
    def clean_tos_confirmed(self):
        data = self.cleaned_data['tos_confirmed']
        if data != True:
            raise forms.ValidationError('You must agree to our Terms Of Service when submitting your registration request')        
        return data

    def clean_password_1(self):
        return clean_password(self.cleaned_data.get('password_1'))

    def clean_password_2(self):
        pw2 = clean_password(self.cleaned_data.get('password_2'))
        if self.clean_password_1() != pw2:
            raise forms.ValidationError("Passwords do not match")
        return pw2

    
    def clean(self):
        super(_BaseForm, self).clean()
        cleaned_data = self.cleaned_data

        return cleaned_data

########################################################################################################    

class ResendConfirmEmailForm(_BaseForm, forms.Form):
    domain_name =  forms.CharField(label='Domain name', max_length=Domain._meta.get_field('name').max_length)

    def clean_domain_name(self):
        data = self.cleaned_data['domain_name'].strip()
        try:
            # Store domain for use in the view function            
            dom = Domain.objects.get(name=data)                        
        except:
            raise forms.ValidationError("We have no record of a request for domain ''"+ data + "'")
        
        self.retrieved_domain = dom              
        if dom.is_active:
                raise forms.ValidationError("Domain '"+ data + "' has already been activated")     
               
        return data    

########################################################################################################

class UpdateSelfForm(_BaseForm, forms.Form):
    first_name  =  forms.CharField(label='First name', max_length=User._meta.get_field('first_name').max_length)
    last_name   =  forms.CharField(label='Last (family) name', max_length=User._meta.get_field('last_name').max_length)
    email       =  forms.EmailField(label ='Email address', max_length=User._meta.get_field('email').max_length)

########################################################################################################                                   

class UpdateSelfTable(tables.Table):
    property = tables.Column(verbose_name="Property")
    old_val= tables.Column(verbose_name="Old value")
    new_val= tables.Column(verbose_name="New value")