import logging
from base64 import b64encode

import bz2
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from django import forms
from django.utils.translation import ugettext_lazy as _

from corehq.apps.dhis2.dbaccessors import get_dhis2_connection, get_dataset_maps
from corehq.apps.dhis2.models import Dhis2Connection, DataSetMap
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

    def save(self, domain_name):
        try:
            dhis2_conn = get_dhis2_connection(domain_name)
            if dhis2_conn is None:
                dhis2_conn = Dhis2Connection(domain=domain_name)
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
    column = forms.CharField(label=_('UCR Column'), required=True)
    data_element_id = forms.CharField(label=_('DataElementID'), required=True)
    category_option_combo_id = forms.CharField(label=_('CategoryOptionComboID'), required=True)
    comment = forms.CharField(label=_('DHIS2 Comment'))

    def __init__(self, *args, **kwargs):
        super(DataValueMapForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            'column',
            'data_element_id',
            'category_option_combo_id',
            'comment',
        )


class DataSetMapForm(forms.Form):
    ucr_id = forms.CharField(label=_('UCR ID'), required=True)

    data_set_id = forms.CharField(label=_('DataSetID'),
                                  help_text=_('Valid if this UCR adds values to an existing DHIS2 DataSet'))

    org_unit_id = forms.CharField(label=_('OrgUnitID'),
                                  help_text=_('Valid if all values are for the same OrganisationUnit'))
    org_unit_column = forms.CharField(label=_('Column containing OrgUnitID'))

    period = forms.CharField(label=_('Period (YYYYMM)'),
                             help_text=_('Valid if all values are for the same Period'))
    period_column = forms.CharField(label=_('Column containing Period'))

    attribute_option_combo_id = forms.CharField(label=_('AttributeOptionComboID'),
                                                help_text=_('Defaults to Category Option Combo in DHIS2'))
    complete_date = forms.CharField(label=_('CompleteDate'))

    def __init__(self, *args, **kwargs):
        super(DataSetMapForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Edit DHIS2 DataSet map'),
                crispy.Field('ucr_id'),
                crispy.Field('data_set_id'),
                crispy.Field('org_unit_id'),
                crispy.Field('org_unit_column'),
                crispy.Field('period'),
                crispy.Field('period_column'),
                crispy.Field('attribute_option_combo_id'),
                crispy.Field('complete_date'),
            ),
        )

    def save(self, domain_name):
        try:
            dataset_maps = get_dataset_maps(domain_name)
            # MVP: For now just one UCR mapped
            dataset_map = dataset_maps[0] if dataset_maps else DataSetMap(domain=domain_name)
            dataset_map.ucr_id = self.cleaned_data['ucr_id']
            dataset_map.data_set_id = self.cleaned_data['data_set_id']
            dataset_map.org_unit_id = self.cleaned_data['org_unit_id']
            dataset_map.org_unit_column = self.cleaned_data['org_unit_column']
            dataset_map.period = self.cleaned_data['period']
            dataset_map.period_column = self.cleaned_data['period_column']
            dataset_map.attribute_option_combo_id = self.cleaned_data['attribute_option_combo_id']
            dataset_map.complete_date = self.cleaned_data['complete_date']

            dataset_map.save()
            return True
        except Exception as err:
            logging.error('Unable to save DHIS2 DataValue map: %s' % err)
            return False
