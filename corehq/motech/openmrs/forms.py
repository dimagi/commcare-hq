from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.openmrs.const import LOG_LEVEL_CHOICES, IMPORT_FREQUENCY_CHOICES
from corehq.motech.openmrs.dbaccessors import get_openmrs_importers_by_domain
from corehq.motech.openmrs.models import OpenmrsImporter, ColumnMapping
from corehq.motech.openmrs.repeater_helpers import PERSON_PROPERTIES, NAME_PROPERTIES, ADDRESS_PROPERTIES
from corehq.motech.utils import b64_aes_encrypt
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from six.moves import map


class OpenmrsConfigForm(forms.Form):
    openmrs_provider = forms.CharField(label=_('Provider UUID'), required=False)
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

    def clean(self):
        cleaned_data = super(OpenmrsImporterForm, self).clean()
        if bool(cleaned_data.get('owner_id')) == bool(cleaned_data.get('location_type_name')):
            message = _(
                'The owner of imported patient cases is determined using either "{owner_id}" or '
                '"{location_type_name}". Please specify either one or the other.').format(
                owner_id=_owner_id_label, location_type_name=_location_type_name_label)
            self.add_error('owner_id', message)
            self.add_error('location_type_name', message)
        return self.cleaned_data

    def save(self, domain_name):
        try:
            importers = get_openmrs_importers_by_domain(domain_name)
            importer = importers[0] if importers else None  # TODO: Support multiple
            if importer is None:
                importer = OpenmrsImporter(domain=domain_name)
            importer.server_url = self.cleaned_data['server_url']
            importer.username = self.cleaned_data['username']
            if self.cleaned_data['password']:
                # Don't save it if it hasn't been changed.
                importer.password = b64_aes_encrypt(self.cleaned_data['password'])
            importer.location_id = self.cleaned_data['location_id']
            importer.import_frequency = self.cleaned_data['import_frequency']
            importer.log_level = self.cleaned_data['log_level']

            importer.report_uuid = self.cleaned_data['report_uuid']
            importer.report_params = self.cleaned_data['report_params']
            importer.case_type = self.cleaned_data['case_type']
            importer.owner_id = self.cleaned_data['owner_id']
            importer.location_type_name = self.cleaned_data['location_type_name']
            importer.external_id_column = self.cleaned_data['external_id_column']
            importer.name_columns = self.cleaned_data['name_columns']
            importer.column_map = list(map(ColumnMapping.wrap, self.cleaned_data['column_map']))
            importer.save()
            return True
        except Exception as err:
            logging.error('Unable to save OpenMRS Importer: %s' % err)
            return False
