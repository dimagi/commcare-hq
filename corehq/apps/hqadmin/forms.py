import re
from django import forms
from django.core.exceptions import ValidationError
from bootstrap3_crispy.bootstrap import StrictButton, FormActions
from bootstrap3_crispy import layout as crispy
from bootstrap3_crispy.helper import FormHelper
from casexml.apps.case.xml import V1, V2


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


class PrimeRestoreCacheForm(forms.Form):
    check_cache_only = forms.BooleanField(
        label='Check cache only',
        help_text="Just check the cache, don't actually generate the restore response.",
        required=False
    )
    domain = forms.CharField(
        label='Domain',
        required=True
    )
    version = forms.ChoiceField(
        label='Output version',
        choices=((V1, V1), (V2, V2)),
        initial=V2
    )
    cache_timeout = forms.IntegerField(
        label='Cache timeout (hours)',
        min_value=1,
        max_value=48,
        initial=24
    )
    overwrite_cache = forms.BooleanField(
        label='Overwrite existing cache',
        help_text=('This will ignore any existing cache and '
                   're-calculate the restore response for each user'),
        required=False
    )
    all_users = forms.BooleanField(
        label='Include all users in the domain',
        required=False
    )
    users = forms.CharField(
        label='User list',
        help_text=('One username or user_id per line '
                   '(username must be full username e.g. test@domain.commcarehq.org)'),
        widget=forms.Textarea(attrs={'rows': '5', 'cols': '50'}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super(PrimeRestoreCacheForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-4'
        self.helper.form_method = 'post'
        self.helper.form_action = '.'
        self.helper.layout = crispy.Layout(
            crispy.Field('check_cache_only', data_ng_model='check_cache_only'),
            crispy.Div(
                'version',
                'cache_timeout',
                'overwrite_cache',
                data_ng_hide='check_cache_only'
            ),
            crispy.Field('all_users', data_ng_model='all_users'),
            'domain',
            crispy.Div('users', data_ng_hide='all_users'),
            FormActions(
                StrictButton(
                    "Submit",
                    css_class="btn-primary",
                    type="submit",
                ),
            ),
        )

    def clean_users(self):
        user_ids = self.cleaned_data['users'].splitlines()
        self.user_ids = filter(None, user_ids)
        return self.cleaned_data['users']

    def clean(self):
        cleaned_data = super(PrimeRestoreCacheForm, self).clean()
        if not self.user_ids and not cleaned_data['all_users']:
            raise forms.ValidationError("Please supply user IDs or select the 'All Users' option")

        if cleaned_data['all_users'] and not cleaned_data['domain']:
            raise forms.ValidationError("Please supply a domain to select users from.")
        return cleaned_data
