import re
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import FormActions
from django import forms
from django.core.exceptions import ValidationError

from corehq.apps.users.models import User


class EmailForm(forms.Form):
    email_subject = forms.CharField(max_length=100)
    email_body = forms.CharField()
    real_email = forms.BooleanField(required=False)


class BrokenBuildsForm(forms.Form):
    builds = forms.CharField(
        widget=forms.Textarea(attrs={'rows': '30', 'cols': '50'})
    )

    def clean_builds(self):
        self.build_ids = re.findall(r'[\w-]+', self.cleaned_data['builds'])
        if not self.build_ids:
            raise ValidationError("You must provide a ")
        return self.cleaned_data['builds']


class AuthenticateAsForm(forms.Form):
    username = forms.CharField(max_length=255)
    domain = forms.CharField(label=u"Domain (used for mobile workers)", max_length=255, required=False)

    def clean(self):
        username = self.cleaned_data['username']
        domain = self.cleaned_data['domain']

        # Ensure that the username exists either as the raw input or with fully qualified name
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            try:
                extended_username = u"{}@{}.commcarehq.org".format(username, domain)
                User.objects.get(username=extended_username)
                self.cleaned_data['username'] = extended_username
            except User.DoesNotExist:
                if domain:
                    raise forms.ValidationError(
                        u"Cannot find user '{}' for domain '{}'".format(username, domain)
                    )
                else:
                    raise forms.ValidationError(u"Cannot find user '{}'".format(username))

        return self.cleaned_data

    def __init__(self, *args, **kwargs):
        super(AuthenticateAsForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            'username',
            'domain',
            crispy.Submit(
                'authenticate_as',
                'Authenticate As'
            )
        )
