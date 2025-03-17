import json

from django import forms
from django.utils.translation import gettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.hqwebapp.utils.translation import format_html_lazy
from corehq.apps.integration.kyc.models import (
    KycConfig,
    KycProviders,
    UserDataStore,
)
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.apps.userreports.ui.fields import JsonField


class KycConfigureForm(forms.ModelForm):

    class Meta:
        model = KycConfig
        fields = [
            'user_data_store',
            'other_case_type',
            'provider',
            'api_field_to_user_data_map',
        ]

    user_data_store = forms.ChoiceField(
        label=_('Recipient Data Store'),
        required=True,
        choices=UserDataStore.CHOICES,
    )
    other_case_type = forms.ChoiceField(
        label=_('Other Case Type'),
        required=False,
    )
    provider = forms.ChoiceField(
        label=_('Provider'),
        required=True,
        choices=KycProviders.choices,
    )
    api_field_to_user_data_map = JsonField(
        label=_('API Field to Recipient Data Map'),
        required=True,
        expected_type=dict,
        help_text=format_html_lazy(
            _('Maps API field for the KYC provider to the field used for storing the relevant data.'
              ' To learn more about this, please have a look at our '
              '<a href="{}" target="_blank">support documentation</a>.'),
            'https://commcare-hq.readthedocs.io/integrations/kyc.html#api-field-to-recipient-data-map'
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = kwargs.pop('instance')

        self.fields['other_case_type'].choices = self._get_case_types()
        self.helper = FormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'user_data_store',
                    x_init='user_data_store = $el.value',
                    x_model='user_data_store',
                ),
                crispy.Div(
                    'other_case_type',
                    x_init='other_case_type = $el.value',
                    x_show='otherCaseTypeChoice === user_data_store',
                ),
                crispy.Div(
                    'provider',
                    x_init='provider = $el.value',
                    x_show='showProvider',
                ),
                crispy.Div(
                    'api_field_to_user_data_map',
                    x_init='api_field_to_user_data_map = $el.value',
                    css_id='api-mapping',
                ),
                twbscrispy.StrictButton(
                    _('Save'),
                    type='submit',
                    css_class='btn btn-primary',
                ),
                x_data=json.dumps({
                    'user_data_store': self.instance.user_data_store,
                    'showProvider': len(KycProviders.choices) > 1,
                    'otherCaseTypeChoice': UserDataStore.OTHER_CASE_TYPE,
                }),
            )
        )

    def _get_case_types(self):
        case_types = sorted(get_case_types_for_domain(self.instance.domain))
        return [
            (case, case) for case in case_types
            if case not in (USERCASE_TYPE, USER_LOCATION_OWNER_MAP_TYPE)
        ]
