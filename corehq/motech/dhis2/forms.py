from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from base64 import b64encode

import bz2
from crispy_forms import (
    layout as crispy,
    bootstrap as twbscrispy,
)
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.dhis2.dbaccessors import get_dhis2_connection
from corehq.motech.dhis2.const import SEND_FREQUENCY_MONTHLY, SEND_FREQUENCY_QUARTERLY
from corehq.motech.dhis2.models import Dhis2Connection
from corehq.apps.hqwebapp import crispy as hqcrispy


SEND_FREQUENCY_CHOICES = (
    (SEND_FREQUENCY_MONTHLY, 'Monthly'),
    (SEND_FREQUENCY_QUARTERLY, 'Quarterly'),
)


class Dhis2ConnectionForm(forms.Form):
    server_url = forms.CharField(label=_('DHIS2 API URL'), required=True,
                                 help_text=_('e.g. "https://play.dhis2.org/demo/api/"'))
    username = forms.CharField(label=_('Username'), required=True)
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput, required=False)
    skip_cert_verify = forms.BooleanField(
        label=_('Skip SSL certificate verification'),
        required=False,
        help_text=_('FOR TESTING ONLY: DO NOT ENABLE THIS FOR PRODUCTION INTEGRATIONS'),
    )

    def __init__(self, *args, **kwargs):
        super(Dhis2ConnectionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Edit DHIS2 connection'),
                crispy.Field('server_url'),
                crispy.Field('username'),
                crispy.Field('password'),
                twbscrispy.PrependedText('skip_cert_verify', ''),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Update DHIS2 connection"),
                    type="submit",
                    css_class='btn-primary',
                )
            ),
        )

    def save(self, domain_name):
        try:
            dhis2_conn = get_dhis2_connection(domain_name)
            if dhis2_conn is None:
                dhis2_conn = Dhis2Connection(domain=domain_name)
            dhis2_conn.server_url = self.cleaned_data['server_url']
            dhis2_conn.username = self.cleaned_data['username']
            if self.cleaned_data['password']:
                # Don't save it if it hasn't been changed. Use simple symmetric encryption. We don't need it to be
                # strong, considering we'd have to store the algorithm and the key together anyway; it just
                # shouldn't be plaintext.
                dhis2_conn.password = b64encode(bz2.compress(self.cleaned_data['password']))
            dhis2_conn.skip_cert_verify = self.cleaned_data['skip_cert_verify']
            dhis2_conn.save()
            return True
        except Exception as err:
            logging.error('Unable to save DHIS2 connection: %s' % err)
            return False


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

            if not form_config.get('program_id'):
                errors.append(ValidationError(
                    '{} {}'.format(required_msg, _('Please specify the DHIS2 Program of the event.')),
                    params={'property': 'program_id'},
                    code='required_property',
                ))
            if not form_config.get('event_date'):
                errors.append(ValidationError(
                    '{} {}'.format(required_msg, _('Please provide a FormQuestion, FormQuestionMap or '
                                                   'ConstantString to determine the date of the event.')),
                    params={'property': 'event_date'},
                    code='required_property',
                ))
            if not form_config.get('datavalue_maps'):
                errors.append(ValidationError(
                    '{} {}'.format(required_msg, _('Please map CommCare values to OpenMRS data elements.')),
                    params={'property': 'datavalue_maps'},
                    code='required_property',
                ))
        if errors:
            raise ValidationError(errors)
        return self.cleaned_data['form_configs']
