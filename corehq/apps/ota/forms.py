from django import forms

# todo proper B3 Handle
from crispy_forms.bootstrap import StrictButton
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from django.utils.translation import ugettext
from corehq.apps.style import crispy as hqcrispy


class PrimeRestoreCacheForm(forms.Form):
    info_text = ugettext(
        "For projects where mobile users manage a lot of cases (e.g. more than 10,000), "
        "this tool can be used to temporarily speed up phone sync times. Once activated, "
        "it will ensure that the 'Sync with Server' functionality runs faster on the phone for 24 hours.")

    def __init__(self, *args, **kwargs):
        super(PrimeRestoreCacheForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.helper.form_method = 'post'
        self.helper.form_action = '.'

        self.helper.layout = crispy.Layout(
            crispy.HTML("<p>" + self.info_text + "</p>"),
            hqcrispy.FormActions(
                StrictButton(
                    "Click here to speed up 'Sync with Server'",
                    css_class="btn-primary",
                    type="submit",
                ),
            ),
        )


class AdvancedPrimeRestoreCacheForm(forms.Form):
    check_cache_only = forms.BooleanField(
        label='Check cache only',
        help_text="Just check the cache, don't actually generate the restore response.",
        required=False
    )
    overwrite_cache = forms.BooleanField(
        label='Overwrite existing cache',
        help_text=('This will ignore any existing cache and '
                   're-calculate the restore response for each user'),
        required=False
    )
    all_users = forms.BooleanField(
        label='Include all users',
        required=False
    )
    users = forms.CharField(
        label='User list',
        help_text=('One username or user_id per line '
                   '(username e.g. mobile_worker_1)'),
        widget=forms.Textarea(attrs={'rows': '5', 'cols': '50'}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super(AdvancedPrimeRestoreCacheForm, self).__init__(*args, **kwargs)
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
            hqcrispy.FormActions(
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
        cleaned_data = super(AdvancedPrimeRestoreCacheForm, self).clean()
        if not self.user_ids and not cleaned_data['all_users']:
            raise forms.ValidationError("Please supply user IDs or select the 'All Users' option")

        return cleaned_data
