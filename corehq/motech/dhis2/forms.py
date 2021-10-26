from typing import Any
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.models import ConnectionSettings

from .const import (
    DHIS2_UID_MESSAGE,
    DHIS2_UID_RE,
    SEND_FREQUENCY_CHOICES,
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
    COMPLETE_DATE_CHOICES,
    COMPLETE_DATE_EMPTY,
    COMPLETE_DATE_COLUMN
)
from .models import SQLDataSetMap, SQLDataValueMap
from corehq.apps.userreports.models import ReportConfiguration
from corehq.util.couch import get_document_or_not_found
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource


class DataSetMapForm(forms.ModelForm):
    description = forms.CharField(
        label=_('Description'),
    )
    frequency = forms.ChoiceField(
        label=_('Frequency'),
        choices=SEND_FREQUENCY_CHOICES,
        initial=SEND_FREQUENCY_MONTHLY,
    )
    day_to_send = forms.CharField(
        label=_('Day to send data'),
        help_text=_('Day of the month if "Frequency" is monthly or quarterly. '
                    'Day of the week if "Frequency" is weekly, where Monday '
                    'is 1 and Sunday is 7.'),
    )
    data_set_id = forms.CharField(
        label=_('DataSetID'),
        help_text=_('The DHIS2 ID of this DataSet'),
        validators=[RegexValidator(DHIS2_UID_RE, DHIS2_UID_MESSAGE)],
        required=True,
    )
    org_unit_id = forms.CharField(
        label=_('OrgUnitID'),
        required=True,
        help_text=_('The UCR column name specifying the OrgUnitID or a static OrgUnitID.'),
    )
    period = forms.CharField(
        label=_('Period'),
        help_text=_('The UCR column name specifying the Period or a static Period. '
                    'Week periods use the format yyyyWn (e.g. "2004W10" for '
                    'week 10, 2004). Month periods use the format yyyyMM '
                    '(e.g. "200403" for March 2004). Quarter periods use the '
                    'format yyyyQn (e.g. "2004Q1" for January-March 2004). '
                    'If the UCR has a date filter then leave the field blank to '
                    'filter the UCR by the date range of the previous '
                    'period.'),
        required=False,
    )
    attribute_option_combo_id = forms.CharField(
        label=_('AttributeOptionComboID'),
        validators=[RegexValidator(DHIS2_UID_RE, DHIS2_UID_MESSAGE)],
        required=False,
    )
    complete_date_option = forms.ChoiceField(
        label=_('CompleteDate'),
        choices=COMPLETE_DATE_CHOICES,
        initial=COMPLETE_DATE_EMPTY,
    )
    complete_date_column = forms.CharField(
        label='CompleteDate Column Name',
        required=False,
    )

    class Meta:
        model = SQLDataSetMap
        fields = [
            'description',
            'connection_settings',
            'ucr_id',
            'frequency',
            'day_to_send',
            'data_set_id',
            'org_unit_id',
            'org_unit_column',
            'period',
            'period_column',
            'attribute_option_combo_id',
            'complete_date_column',
            'complete_date_option',
        ]

    def __init__(self, domain, *args, **kwargs):
        from corehq.motech.dhis2.views import DataSetMapListView
        kwargs['initial'] = add_initial_properties(kwargs.get('instance'), kwargs.get('initial'))

        super().__init__(*args, **kwargs)
        self.domain = domain
        self.fields['connection_settings'] = get_connection_settings_field(domain)
        self.fields['ucr_id'] = get_ucr_field(domain)

        self.helper = hqcrispy.HQFormHelper()

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('DataSet Details'),
                crispy.Field('description'),
                crispy.Field('connection_settings'),
                crispy.Field('ucr_id'),
                crispy.Field('frequency'),
                crispy.Field('day_to_send'),
                crispy.Field('data_set_id'),
                crispy.Field('org_unit_id'),
                crispy.Field('period'),
                crispy.Field('attribute_option_combo_id'),
                crispy.Field('complete_date_option'),
                crispy.Field('complete_date_column'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                hqcrispy.LinkButton(
                    _("Cancel"),
                    reverse(
                        DataSetMapListView.urlname,
                        kwargs={'domain': self.domain},
                    ),
                    css_class="btn btn-default",
                ),
            ),
        )

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)

    def clean(self):
        cleaned_data = super().clean()

        if (
            cleaned_data.get('frequency') == SEND_FREQUENCY_WEEKLY
            and not _int_in_range(cleaned_data.get('day_to_send'), 1, 7)
        ):
            self.add_error('day_to_send', _(
                'Enter a day of the week, where Monday is 1 and Sunday is 7.'
            ))

        elif (
            cleaned_data.get('frequency') != SEND_FREQUENCY_WEEKLY
            and not _int_in_range(cleaned_data.get('day_to_send'), 1, 28)
        ):
            self.add_error('day_to_send', _(
                'Enter a day of the month that occurs in every month (i.e. '
                'from 1 to 28).'
            ))

        ucr_id = cleaned_data.get('ucr_id')
        ucr = None
        if ucr_id:
            ucr = get_document_or_not_found(ReportConfiguration, self.domain, ucr_id)

        if cleaned_data.get('org_unit_id'):
            org_unit_id = cleaned_data.get('org_unit_id')

            # Check if the user input corresponds to one of the UCR's columns
            # If so, populate 'org_unit_column', else 'org_unit_id'
            if ucr_has_field(ucr, org_unit_id):
                # Save user period input appropriately as period_column
                cleaned_data['org_unit_column'] = cleaned_data['org_unit_id']
                cleaned_data['org_unit_id'] = None

            else:
                try:
                    org_unit_validator = RegexValidator(DHIS2_UID_RE, DHIS2_UID_MESSAGE)
                    org_unit_validator(org_unit_id)
                    # Ensure org_unit_column and org_unit_id is not both saved
                    if cleaned_data['org_unit_column']:
                        cleaned_data['org_unit_column'] = None

                except ValidationError:
                    self.add_error('org_unit_id', org_unit_validator.message)

        if cleaned_data.get('period'):
            period = cleaned_data.get('period')

            # Check if the user input corresponds to one of the UCR's columns
            # If so, populate 'period_column', else 'period'
            if ucr_has_field(ucr, period):
                # Save user period input appropriately as period_column
                cleaned_data['period_column'] = cleaned_data['period']
                cleaned_data['period'] = None

            else:
                period_validators = {
                    SEND_FREQUENCY_WEEKLY: RegexValidator(r'^\d{4}W\d{1,2}$', _(
                        '"Frequency" is set to "Weekly". Please enter a valid '
                        'week period in the format yyyyWn (e.g. "2004W10" for '
                        'week 10, 2004), or enter a valid column.'
                    )),
                    SEND_FREQUENCY_MONTHLY: RegexValidator(r'^\d{6}$', _(
                        '"Frequency" is set to "Monthly". Please enter a valid '
                        'month period in the format yyyyMM (e.g. "200403" for '
                        'March 2004), or enter a valid column.'
                    )),
                    SEND_FREQUENCY_QUARTERLY: RegexValidator(r'^\d{4}Q\d$', _(
                        '"Frequency" is set to "Quarterly". Please enter a valid '
                        'quarter period in the format yyyyQn (e.g. "2004Q1" for '
                        'January-March 2004), or enter a valid column.'
                    )),
                }
                validate_period = period_validators[cleaned_data.get('frequency')]
                try:
                    validate_period(cleaned_data.get('period'))

                    # Ensure period column and period is not both saved
                    if cleaned_data['period_column'] is not None:
                        cleaned_data['period_column'] = None

                except ValidationError:
                    self.add_error('period', validate_period.message)

        selected_complete_date_option = cleaned_data.get('complete_date_option')

        if selected_complete_date_option == COMPLETE_DATE_COLUMN:
            column_name = cleaned_data.get('complete_date_column')

            if not column_name:
                self.add_error('complete_date_column', 'Cannot be empty.')
            elif ucr_has_field(ucr, column_name):
                if valid_ucr_date_column(ucr, column_name):
                    cleaned_data['complete_date_column'] = column_name
                else:
                    self.add_error(
                        'complete_date_column',
                        'Please make sure the column values are formatted as yyyy-mm-dd'
                    )
            else:
                self.add_error('complete_date_column', 'Column does not exist in UCR.')
        else:
            cleaned_data['complete_date_column'] = None

        return self.cleaned_data


def add_initial_properties(instance, kwargs_initial):
    if instance is not None:
        if instance.period_column:
            kwargs_initial['period'] = instance.period_column

        if instance.org_unit_column:
            kwargs_initial['org_unit_id'] = instance.org_unit_column

    return kwargs_initial


def ucr_has_field(ucr: ReportConfiguration, field):
    return any(c.column_id == field for c in ucr.report_columns)


def valid_ucr_date_column(ucr, column_name):
    data_source = ConfigurableReportDataSource.from_spec(ucr, include_prefilters=True)

    for datum in data_source.get_data():
        value = datum.get(column_name)

        try:
            if type(value) is not str:
                return False
            else:
                datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return False
    return True


def get_connection_settings_field(domain):
    from corehq.motech.views import ConnectionSettingsListView

    connection_settings = ConnectionSettings.objects.filter(domain=domain)
    url = reverse(ConnectionSettingsListView.urlname,
                  kwargs={'domain': domain})
    return forms.ModelChoiceField(
        label=_("Connection Settings"),
        queryset=connection_settings,
        required=True,
        help_text=_(f'<a href="{url}">Add/Edit Connections Settings</a>')
    )


def get_ucr_field(domain):
    from corehq.apps.userreports.views import UserConfigReportsHomeView

    ucrs = get_report_configs_for_domain(domain)
    url = reverse(UserConfigReportsHomeView.urlname,
                  kwargs={'domain': domain})
    return forms.ChoiceField(
        label=_("User Configurable Report"),
        choices=[(ucr.get_id, ucr.title) for ucr in ucrs],
        required=True,
        help_text=_(
            'DataSet Maps map CommCare UCRs to DHIS2 DataSets. '
            '<a href="https://github.com/dimagi/commcare-hq/blob/master/corehq/motech/dhis2/README.md#datasets" '
            f'target="_new">More info</a>. '
            f'Go to <a href="{url}">Configurable Reports</a> to define a UCR.')
    )


class DataValueMapBaseForm(forms.ModelForm):
    column = forms.CharField(
        label=_('Column'),
        required=True,
    )
    data_element_id = forms.CharField(
        label=_('Data element ID'),
        required=True,
        validators=[RegexValidator(DHIS2_UID_RE, DHIS2_UID_MESSAGE)],
    )
    category_option_combo_id = forms.CharField(
        label=_('Category option combo ID'),
        required=False,
        validators=[RegexValidator(DHIS2_UID_RE, DHIS2_UID_MESSAGE)],
    )
    comment = forms.CharField(
        label=_('Comment'),
        required=False,
    )

    class Meta:
        model = SQLDataValueMap
        fields = [
            'column',
            'data_element_id',
            'category_option_combo_id',
            'comment',
        ]

    def __init__(self, dataset_map, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dataset_map = dataset_map
        self.helper = self.get_form_helper()

    def get_form_helper(self):
        raise NotImplementedError

    def save(self, commit=True):
        self.instance.dataset_map = self.dataset_map
        return super().save(commit)


class DataValueMapCreateForm(DataValueMapBaseForm):

    def get_form_helper(self):
        helper = FormHelper()
        helper.form_style = 'inline'
        helper.form_show_labels = False
        helper.layout = crispy.Layout(
            twbscrispy.InlineField('column'),
            twbscrispy.InlineField('data_element_id'),
            twbscrispy.InlineField('category_option_combo_id'),
            twbscrispy.InlineField('comment'),
            twbscrispy.StrictButton(
                mark_safe(f'<i class="fa fa-plus"></i> {_("Add")}'),  # nosec: no user input
                css_class='btn-primary',
                type='submit',
            )
        )
        return helper


class DataValueMapUpdateForm(DataValueMapBaseForm):
    id = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = SQLDataValueMap
        fields = [
            'id',
            'column',
            'data_element_id',
            'category_option_combo_id',
            'comment',
        ]

    def get_form_helper(self):
        helper = FormHelper()
        helper.form_style = 'default'
        helper.form_show_labels = True
        helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field('id'),
                crispy.Field('column'),
                crispy.Field('data_element_id'),
                crispy.Field('category_option_combo_id'),
                crispy.Field('comment'),
                css_class='modal-body',
            ),
            twbscrispy.FormActions(
                twbscrispy.StrictButton(
                    "Update DataValue Map",
                    css_class='btn btn-primary',
                    type='submit',
                ),
                crispy.HTML('<button type="button" '
                            '        class="btn btn-default" '
                            '        data-dismiss="modal">'
                            'Cancel'
                            '</button>'),
                css_class='modal-footer',
            )
        )
        return helper


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


def _int_in_range(value: Any, lower: int, upper: int) -> bool:
    """
    Casts as int and returns True if lower <= value <= upper

    >>> _int_in_range(5, 1, 7)
    True

    """
    try:
        value_int = int(value)
    except (TypeError, ValueError):
        return False
    return lower <= value_int <= upper
