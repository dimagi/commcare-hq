from django import forms
from django.contrib.auth.models import User
from corehq.apps.domain.forms import clean_password, max_pwd, _BaseForm
from django.core.validators import validate_email

class NewWebUserRegistrationForm(forms.Form):
    """
    Form for a brand new user, before they've created a domain or done anything on CommCare HQ.
    """
    full_name = forms.CharField(label='Full Name', max_length=User._meta.get_field('first_name').max_length+User._meta.get_field('last_name').max_length+1)
    email = forms.EmailField(label='Email Address',
                                    max_length=User._meta.get_field('email').max_length,
                                    help_text='You will use this to log in')
    password  =  forms.CharField(label='Password', max_length=max_pwd, widget=forms.PasswordInput(render_value=False))

    def clean_full_name(self):
        data = self.cleaned_data['full_name'].split()
        return [data.pop(0)] + [' '.join(data)]

    def clean_email(self):
        data = self.cleaned_data['email'].strip()
        validate_email(data)
        if User.objects.filter(username__iexact=data).count() > 0:
            raise forms.ValidationError('Username already taken; please try another')
        return data

    def clean_password(self):
        return clean_password(self.cleaned_data.get('password'))

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data