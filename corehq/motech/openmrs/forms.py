from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.openmrs.const import (
    ADDRESS_PROPERTIES,
    IMPORT_FREQUENCY_CHOICES,
    LOG_LEVEL_CHOICES,
    NAME_PROPERTIES,
    PERSON_PROPERTIES,
)


class OpenmrsConfigForm(forms.Form):
    openmrs_provider = forms.CharField(label=_("Provider UUID"), required=False)
    case_config = JsonField(expected_type=dict)
    form_configs = JsonField(expected_type=list)

    def __init__(self, *args, **kwargs):
        super(OpenmrsConfigForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', _('Save Changes')))

    def clean_case_config(self):

        for key in self.cleaned_data['case_config']['person_properties']:
            if key not in PERSON_PROPERTIES:
                raise ValidationError(
                    _('person property key "%(key)s" is not valid.'),
                    code='invalid',
                    params={'key': key}
                )

        for key in self.cleaned_data['case_config']['person_preferred_name']:
            if key not in NAME_PROPERTIES:
                raise ValidationError(
                    _('person preferred name key "%(key)s" is not valid.'),
                    code='invalid',
                    params={'key': key}
                )

        for key in self.cleaned_data['case_config']['person_preferred_address']:
            if key not in ADDRESS_PROPERTIES:
                raise ValidationError(
                    _('person preferred address key "%(key)s" is not valid.'),
                    code='invalid',
                    params={'key': key}
                )

        for id_ in self.cleaned_data['case_config']['match_on_ids']:
            if id_ not in self.cleaned_data['case_config']['patient_identifiers']:
                raise ValidationError(
                    _('ID "%(id_)s" used in "match_on_ids" is missing from "patient_identifiers".'),
                    code='invalid',
                    params={'id_': id_}
                )

        return self.cleaned_data['case_config']


_owner_id_label = _('Owner ID')
_location_type_name_label = _('Organization Level')


class OpenmrsImporterForm(forms.Form):
    server_url = forms.CharField(label=_('OpenMRS URL'), required=True,
                                 help_text=_('e.g. "http://www.example.com/openmrs"'))
    username = forms.CharField(label=_('Username'), required=True)
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput, required=False)
    location_id = forms.CharField(label=_('Location ID'), required=False,
                                  help_text='If a project space has multiple OpenMRS servers to import from, for '
                                            'which CommCare location is this OpenMRS server authoritative?')
    import_frequency = forms.ChoiceField(label=_('Import Frequency'), choices=IMPORT_FREQUENCY_CHOICES,
                                         help_text=_('How often should cases be imported?'), required=False)
    log_level = forms.TypedChoiceField(label=_('Log Level'), required=False, choices=LOG_LEVEL_CHOICES, coerce=int)
    timezone = forms.CharField(label=_('Timezone'), required=False,
                               help_text=_("Timezone name. If not specified, the domain's timezone will be used."))

    report_uuid = forms.CharField(label=_('Report UUID'), required=True,
                                  help_text=_('The OpenMRS UUID of the report of patients to be imported'))
    report_params = JsonField(label=_('Report Parameters'), required=False, expected_type=dict)
    case_type = forms.CharField(label=_('Case Type'), required=True)
    owner_id = forms.CharField(label=_owner_id_label, required=False,
                               help_text=_('The ID of the mobile worker or location who will own new cases'))
    location_type_name = forms.CharField(label=_location_type_name_label, required=False,
                                         help_text=_('The Organization Level whose mobile worker will own new '
                                                     'cases'))
    external_id_column = forms.CharField(label=_('External ID Column'), required=True,
                                         help_text=_("The column that contains the OpenMRS UUID of the patient"))
    name_columns = forms.CharField(label=_('Name Columns'), required=True,
                                   help_text=_('Space-separated column(s) to be concatenated to create the case '
                                               'name (e.g. "givenName familyName")'))
    column_map = JsonField(label=_('Map columns to properties'), required=True, expected_type=list,
                           help_text=_('e.g. [{"column": "givenName", "property": "first_name"}, ...]'))
