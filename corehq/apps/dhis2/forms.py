import logging
from base64 import b64encode

import bz2
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from django import forms
from django.utils.translation import ugettext_lazy as _

from corehq.apps.dhis2.dbaccessors import get_dhis2_connection, get_datavalue_maps
from corehq.apps.dhis2.models import Dhis2Connection, DataValueMap
from corehq.apps.style import crispy as hqcrispy


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
            dhis2_conn = get_dhis2_connection(domain.name)
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


class DataValueMapForm(forms.Form):
    report = forms.UUIDField()  # a UCR
    data_element_column = forms.CharField(label=_('Column containing Data Element ID'), required=True)
    # period_column # MVP: report (month) period as YYYYMM
    org_unit_column = forms.CharField(label=_('Column containing Org Unit ID'), required=True)
    category_option_combo_column = forms.CharField(label=_('Column containing Category Option Combo ID'),
                                                   required=True)
    value_column = forms.CharField(label=_('Column containing Value'), required=True)
    complete_date_column = forms.CharField(label=_('Column containing Complete Date'))
    attribute_option_combo_column = forms.CharField(label=_('Column containing Attribute Option Combo ID'),
                                                    help_text=_('Defaults to Category Option Combo in DHIS2'))
    comment_column = forms.CharField(label=_('Column containing Comment'))

    def __init__(self, *args, **kwargs):
        super(DataValueMapForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Edit DHIS2 DataValue map'),
                crispy.Field('report'),
                crispy.Field('data_element_column'),

                crispy.Field('org_unit_column'),
                crispy.Field('category_option_combo_column'),
                crispy.Field('value_column'),

                crispy.Field('complete_date_column'),
                crispy.Field('attribute_option_combo_column'),
                crispy.Field('comment_column'),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update DHIS2 DataValue map"),
                    type="submit",
                    css_class='btn-primary',
                )
            ),
        )

    def save(self, domain):
        try:
            try:
                # No reason we can't have many per domain, but for the MVP just offer one.
                datavalue_map = get_datavalue_maps(domain.name)[0]
            except IndexError:
                datavalue_map = None

            if datavalue_map is None:
                datavalue_map = DataValueMap(domain=domain.name)
            datavalue_map.report = self.cleaned_data['report']
            datavalue_map.data_element_column = self.cleaned_data['data_element_column']
            datavalue_map.org_unit_column = self.cleaned_data['org_unit_column']
            datavalue_map.category_option_combo_column = self.cleaned_data['category_option_combo_column']
            datavalue_map.value_column = self.cleaned_data['value_column']
            datavalue_map.complete_date_column = self.cleaned_data['complete_date_column']
            datavalue_map.attribute_option_combo_column = self.cleaned_data['attribute_option_combo_column']
            datavalue_map.comment_column = self.cleaned_data['comment_column']
            datavalue_map.save()
            return True
        except Exception as err:
            logging.error('Unable to save DHIS2 DataValue map: %s' % err)
            return False
