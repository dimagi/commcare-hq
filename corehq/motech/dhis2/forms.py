from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.dhis2.const import (
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
)

SEND_FREQUENCY_CHOICES = (
    (SEND_FREQUENCY_MONTHLY, 'Monthly'),
    (SEND_FREQUENCY_QUARTERLY, 'Quarterly'),
)


class Dhis2ConfigForm(forms.Form):
    form_configs = JsonField(expected_type=list)

    def __init__(self, *args, **kwargs):
        super(Dhis2ConfigForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', _('Save Changes')))

    def clean_form_configs(self):
        errors = []
        for form_config in self.cleaned_data['form_configs']:
            if form_config.get('xmlns'):
                required_msg = _('The "%(property)s" property is required for '
                                 'form "{}".').format(form_config['xmlns'])
            else:
                required_msg = _('The "%(property)s" property is required.')

            if not form_config.get('xmlns'):
                errors.append(ValidationError(
                    '{} {}'.format(required_msg, _('Please specify the XMLNS of the form.')),
                    params={'property': 'xmlns'},
                    code='required_property',
                ))
            if not form_config.get('program_id'):
                errors.append(ValidationError(
                    '{} {}'.format(required_msg, _('Please specify the DHIS2 Program of the event.')),
                    params={'property': 'program_id'},
                    code='required_property',
                ))
            if not form_config.get('datavalue_maps'):
                errors.append(ValidationError(
                    '{} {}'.format(required_msg, _('Please map CommCare values to DHIS2 data elements.')),
                    params={'property': 'datavalue_maps'},
                    code='required_property',
                ))
        if errors:
            raise ValidationError(errors)
        return self.cleaned_data['form_configs']
