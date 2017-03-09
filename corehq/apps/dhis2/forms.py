import logging
from base64 import b64encode

import bz2
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from django import forms
from django.utils.translation import ugettext_lazy as _

from corehq.apps.style import crispy as hqcrispy
from corehq.apps.dhis2.models import Dhis2Connection


class Dhis2ConnectionForm(forms.Form):
    server_url = forms.CharField(label=_('DHIS2 Server URL'), required=True)
    username = forms.CharField(label=_('Username'), required=True)
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput, required=True)

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
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update DHIS2 connection"),
                    type="submit",
                    css_class='btn-primary',
                )
            ),
        )

    def save(self, domain):
        try:
            dhis2_conn = Dhis2Connection.for_domain(domain.name)
            if dhis2_conn is None:
                dhis2_conn = Dhis2Connection(domain=domain.name)
            dhis2_conn.server_url = self.cleaned_data['server_url']
            dhis2_conn.username = self.cleaned_data['username']
            if self.cleaned_data['password']:
                # Simple symmetric encryption. We don't need it to be strong, considering we'd have to store the
                # algorithm and the key together anyway; it just shouldn't be plaintext.
                dhis2_conn.password = b64encode(bz2.compress(self.cleaned_data['password']))
            dhis2_conn.save()
            return True
        except Exception as err:
            logging.error('Unable to save DHIS2 connection: %s' % err)
            return False
