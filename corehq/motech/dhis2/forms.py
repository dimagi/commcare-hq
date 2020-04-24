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
        errors = _validate_form_configs(self.cleaned_data['form_configs'])
        if errors:
            raise ValidationError(errors)
        return self.cleaned_data['form_configs']


class Dhis2EntityConfigForm(forms.Form):
    """
    Dhis2EntityConfig.case_configs is a list. Dhis2EntityConfigForm has
    one case_config, and is used in a formset.
    """
    case_config = JsonField()

    def clean_case_config(self):
        errors = []
        case_config = self.cleaned_data['case_config']
        if not isinstance(case_config, dict):
            raise ValidationError(
                _('The "case_type" property is a dictionary, not a "%(data_type)s".'),
                params={'data_type': type(case_config).__name__}
            )
        if not case_config.get('case_type'):
            errors.append(ValidationError(
                _('The "%(property)s" property is required.'),
                params={'property': 'case_type'},
                code='required_property',
            ))
        if 'form_configs' not in case_config:
            errors.append(ValidationError(
                _('The "%(property)s" property is required.'),
                params={'property': 'form_configs'},
                code='required_property',
            ))
        elif not isinstance(case_config['form_configs'], list):
            raise ValidationError(
                _('The "form_configs" property is a dictionary, not a "%(data_type)s".'),
                params={'data_type': type(case_config['form_configs']).__name__}
            )
        else:
            errors.extend(_validate_form_configs(case_config['form_configs']))
        if errors:
            raise ValidationError(errors)
        return self.cleaned_data['case_config']


def _validate_form_configs(form_configs):
    errors = []
    for form_config in form_configs:
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
    return errors
