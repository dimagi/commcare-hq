from base64 import b64encode
import bz2
import logging
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.style import crispy as hqcrispy
from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.openmrs.const import LOG_LEVEL_CHOICES, IMPORT_FREQUENCY_CHOICES
from corehq.motech.openmrs.dbaccessors import get_openmrs_importers_by_domain
from corehq.motech.openmrs.models import OpenmrsImporter
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class OpenmrsConfigForm(forms.Form):
    case_config = JsonField(expected_type=dict)
    form_configs = JsonField(expected_type=list)

    def __init__(self, *args, **kwargs):
        super(OpenmrsConfigForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', _('Save Changes')))


class OpenmrsImporterForm(forms.Form):
    server_url = forms.CharField(label=_('OpenMRS URL'), required=True,
                                 help_text=_('e.g. "http://www.example.com/openmrs"'))
    username = forms.CharField(label=_('Username'), required=True)
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput, required=False)
    log_level = forms.TypedChoiceField(label=_('Log Level'), required=False, choices=LOG_LEVEL_CHOICES, coerce=int)
    report_uuid = forms.CharField(label=_('Report UUID'), required=True,
                                  help_text=_('The OpenMRS UUID of the report of patients to be imported'))
    case_type = forms.CharField(label=_('Case Type'), required=True)
    owner_id = forms.CharField(label=_('Owner ID'), required=True,
                               help_text=_('The ID of the mobile worker or location who will own new cases'))
    import_frequency = forms.ChoiceField(label=_('Import Frequency'), choices=IMPORT_FREQUENCY_CHOICES,
                                         help_text=_('How often should cases be imported?'), required=False)

    def __init__(self, *args, **kwargs):
        super(OpenmrsImporterForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Edit OpenMRS Importer'),
                crispy.Field('server_url'),
                crispy.Field('username'),
                crispy.Field('password'),
                crispy.Field('log_level'),
                crispy.Field('report_uuid'),
                crispy.Field('case_type'),
                crispy.Field('owner_id'),
                crispy.Field('import_frequency'),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update OpenMRS Importer"),
                    type="submit",
                    css_class='btn-primary',
                )
            ),
        )

    def save(self, domain_name):
        try:
            importers = get_openmrs_importers_by_domain(domain_name)
            importer = importers[0] if importers else None  # TODO: Support multiple
            if importer is None:
                importer = OpenmrsImporter(domain=domain_name)
            importer.server_url = self.cleaned_data['server_url']
            importer.username = self.cleaned_data['username']
            if self.cleaned_data['password']:
                # Don't save it if it hasn't been changed. Use simple symmetric encryption. We don't need it to be
                # strong, considering we'd have to store the algorithm and the key together anyway; it just
                # shouldn't be plaintext.
                importer.password = b64encode(bz2.compress(self.cleaned_data['password']))
            importer.log_level = self.cleaned_data['log_level']
            importer.report_uuid = self.cleaned_data['report_uuid']
            importer.case_type = self.cleaned_data['case_type']
            importer.owner_id = self.cleaned_data['owner_id']
            importer.import_frequency = self.cleaned_data['import_frequency']
            importer.save()
            return True
        except Exception as err:
            logging.error('Unable to save OpenMRS Importer: %s' % err)
            return False
