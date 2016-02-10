import re
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django import forms
from django.core.exceptions import ValidationError

from corehq.apps.users.models import CommCareUser


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
        if domain:
            extended_username = u"{}@{}.commcarehq.org".format(username, domain)
            user = CommCareUser.get_by_username(username=extended_username)
            self.cleaned_data['username'] = extended_username
            if user is None:
                raise forms.ValidationError(
                    u"Cannot find user '{}' for domain '{}'".format(username, domain)
                )
        else:
            user = CommCareUser.get_by_username(username=username)
            if user is None:
                raise forms.ValidationError(u"Cannot find user '{}'".format(username))

        if not user.is_commcare_user():
            raise forms.ValidationError(u"User '{}' is not a CommCareUser".format(username))

        return self.cleaned_data

    def __init__(self, *args, **kwargs):
        super(AuthenticateAsForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_id = 'auth-as-form'
        self.helper.layout = crispy.Layout(
            'username',
            'domain',
            crispy.Submit(
                'authenticate_as',
                'Authenticate As'
            )
        )
