from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.dhis2.const import SEND_FREQUENCY_CHOICES
from corehq.motech.forms import get_conns_field


class DatasetMapForm(forms.Form):
    description = forms.CharField()
    frequency = forms.ChoiceField(choices=SEND_FREQUENCY_CHOICES)
    connection_settings_id = forms.ChoiceField()
    ucr_id = forms.ChoiceField()
    day_to_send = forms.IntegerField(help_text=_(
        'Day of the month if Frequency is monthly or quarterly. Day of '
        'the week if Frequency is weekly, where Monday is 1 and Sunday is '
        '7.'
    ))
    data_set_id = forms.CharField(help_text=_(
        'Set this if this UCR adds values to an existing DHIS2 DataSet.'
    ))
    org_unit_column = forms.CharField(help_text=_(
        'UCR column where OrganisationUnit ID can be found'

    ))
    org_unit_id = forms.CharField(help_text=_(
        'Set this if all values are for the same OrganisationUnit.'
    ))
    period_column = forms.CharField(help_text=_(
        'UCR column where the period can be found'

    ))
    period = forms.CharField(help_text=_(
        'Set this if all values are for the same period. Monthly uses format '
        '"YYYYMM". Quarterly uses format "YYYYQ#".'
    ))

    attribute_option_combo_id = forms.CharField(help_text=_(
        'Optional. DHIS2 defaults this to categoryOptionCombo'
    ))
    complete_date = forms.CharField(help_text=_('Optional'))

    # TODO: datavalue_maps is a paginated list
    # datavalue_maps = SchemaListProperty(DataValueMap)

    def __init__(self, *args, **kwargs):
        from corehq.motech.dhis2.views import DataSetMapListView

        self.domain = kwargs.pop('domain')
        super().__init__(*args, **kwargs)

        self.fields['connection_settings_id'] = get_conns_field(self.domain)
        self.fields['ucr_id'] = get_ucr_field(self.domain)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('DataSet Map'),
                crispy.Field('description'),
                self.refresh_metadata_button,
                crispy.Field('frequency'),
                crispy.Field('day_to_send'),
                crispy.Field('data_set_id'),

                crispy.Field('org_unit_column'),
                crispy.Field('org_unit_id'),

                crispy.Field('period_column'),
                crispy.Field('period'),

                crispy.Field('attribute_option_combo_id'),

                crispy.Field('complete_date'),
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

    @property
    def refresh_metadata_button(self):
        return crispy.Div(
            crispy.Div(
                twbscrispy.StrictButton(
                    _('Test Connection'),
                    type='button',
                    css_id='test-connection-button',
                    css_class='btn btn-default disabled',
                ),
                crispy.Div(
                    css_id='test-connection-result',
                    css_class='text-success hide',
                ),
                css_class=hqcrispy.CSS_ACTION_CLASS,
            ),
            css_class='form-group'
        )


def get_ucr_field(domain: str) -> forms.ChoiceField:
    from corehq.apps.userreports.views import UserConfigReportsHomeView

    ucrs = get_report_configs_for_domain(domain)
    url = reverse(UserConfigReportsHomeView.urlname, kwargs={'domain': domain})
    return forms.ChoiceField(
        label=_("User Configurable Report"),
        choices=[(r._id, r.title) for r in ucrs],
        required=True,
        help_text=f'<a href="{url}">'
                  + _('Add/Edit User Configurable Reports')
                  + '</a>'
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
