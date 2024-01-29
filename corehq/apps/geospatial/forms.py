from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django import forms
from corehq.apps.geospatial.models import GeoConfig
from corehq import toggles


LOCATION_SOURCE_OPTIONS = [
    (GeoConfig.CUSTOM_USER_PROPERTY, _("Custom user field")),
    (GeoConfig.ASSIGNED_LOCATION, _("User's assigned location")),
]


class GeospatialConfigForm(forms.ModelForm):

    RADIAL_ALGORITHM_OPTION = (GeoConfig.RADIAL_ALGORITHM, _('Radial Algorithm'))
    ROAD_NETWORK_ALGORITHM_OPTION = (GeoConfig.ROAD_NETWORK_ALGORITHM, _('Road Network Algorithm'))

    DISBURSEMENT_ALGORITHM_OPTIONS = [
        RADIAL_ALGORITHM_OPTION,
    ]

    class Meta:
        model = GeoConfig
        fields = [
            "user_location_property_name",
            "case_location_property_name",
            "selected_grouping_method",
            "max_cases_per_group",
            "min_cases_per_group",
            "target_group_count",
            "selected_disbursement_algorithm",
            "plaintext_api_token",
        ]

    user_location_property_name = forms.CharField(
        label=_("Fetch mobile worker location data from custom field"),
        required=True,
        help_text=_("The name of the mobile worker custom field which stores the users' geo-location data."),
    )
    case_location_property_name = forms.CharField(
        label=_("Fetch case location data from property"),
        widget=forms.widgets.Select(choices=[]),
        required=True,
        help_text=_("The name of the case property storing the geo-location data of your cases."),
    )
    selected_grouping_method = forms.ChoiceField(
        label=_("Grouping method"),
        # TODO: Add relevant documentation link to help_text when geospatial feature is GA'ed
        help_text=_("Determines which parameter to use for grouping cases"),
        required=False,
        choices=GeoConfig.VALID_GROUPING_METHODS,
    )
    max_cases_per_group = forms.IntegerField(
        label=_("Maximum group size"),
        help_text=_("The maximum number of cases that can be in a group"),
        required=False,
        min_value=1,
    )
    min_cases_per_group = forms.IntegerField(
        label=("Minimum group size"),
        help_text=_("The minimum number of cases that can be in a group"),
        required=False,
        min_value=1,
    )
    target_group_count = forms.IntegerField(
        label=_("Target group count"),
        help_text=_("The desired number of groups. Cases will be divided equally to create this many groups"),
        required=False,
        min_value=1,
    )
    selected_disbursement_algorithm = forms.ChoiceField(
        label=_("Disbursement algorithm"),
        # TODO: Uncomment once linked documentation becomes public (geospatial feature is GA'ed)
        # help_text=format_html_lazy(
        #     _('For more information on these algorithms please look at our '
        #       '<a href="{}" target="_blank">support documentation</a>.'),
        #     'https://confluence.dimagi.com/pages/viewpage.action?pageId=164694245'
        # ),
        choices=DISBURSEMENT_ALGORITHM_OPTIONS,
        required=True,
    )
    plaintext_api_token = forms.CharField(
        label=_("Enter mapbox token"),
        help_text=_(
            "Enter your Mapbox API token here. Make sure your token has the correct scope configured"
            " for use of the Mapbox Matrix API."
        ),
        required=False,
        widget=forms.PasswordInput(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if toggles.SUPPORT_ROAD_NETWORK_DISBURSEMENT_ALGORITHM.enabled(self.domain):
            choices = self.fields['selected_disbursement_algorithm'].choices
            choices.append(self.ROAD_NETWORK_ALGORITHM_OPTION)
            self.fields['selected_disbursement_algorithm'].choices = choices

        self.helper = hqcrispy.HQFormHelper()
        self.helper.add_layout(
            crispy.Layout(
                crispy.Fieldset(
                    _("Configure Geospatial Settings"),
                    crispy.Field(
                        'user_location_property_name',
                        data_bind="value: customUserFieldName"
                    ),
                    crispy.Field(
                        'case_location_property_name',
                        data_bind="options: geoCasePropOptions, "
                                  "value: geoCasePropertyName, "
                                  "event: {change: onGeoCasePropChange}"
                    ),
                    crispy.Div(
                        crispy.HTML('%s' % _(
                            'The currently used "{{ config.case_location_property_name }}" case property '
                            'has been deprecated in the Data Dictionary. Please consider switching this '
                            'to another property.')
                        ),
                        css_class='alert alert-warning',
                        data_bind="visible: isCasePropDeprecated"
                    ),
                    crispy.Div(
                        crispy.HTML('%s' % _(
                            'The currently used "{{ config.case_location_property_name }}" case '
                            'property may be associated with cases. Selecting a new case '
                            'property will have the following effects:'
                            '<ul><li>All cases using the old case property will no longer appear on maps.</li>'
                            '<li>If the old case property is being used in an application, a new version would '
                            'need to be released with the new case property for all users that capture '
                            'location data.</li></ul>')
                        ),
                        css_class='alert alert-warning',
                        data_bind="visible: hasGeoCasePropChanged"
                    ),
                ),
                crispy.Fieldset(
                    _('Case Grouping Parameters'),
                    crispy.Field('selected_grouping_method', data_bind="value: selectedGroupMethod"),
                    crispy.Div(
                        crispy.Field('max_cases_per_group'),
                        crispy.Field('min_cases_per_group'),
                        data_bind='visible: isMinMaxGrouping',
                    ),
                    crispy.Div(
                        crispy.Field('target_group_count'),
                        data_bind='visible: isTargetGrouping',
                    ),
                ),
                crispy.Fieldset(
                    _('Algorithms'),
                    crispy.Field(
                        'selected_disbursement_algorithm',
                        data_bind='value: selectedAlgorithm',
                    ),
                    crispy.Div(
                        crispy.Field('plaintext_api_token', data_bind="value: plaintext_api_token"),
                        data_bind="visible: captureApiToken"
                    ),
                    crispy.Div(
                        StrictButton(
                            _('Test API Key'),
                            type='button',
                            css_id='test-connection-button',
                            css_class='btn btn-default',
                            data_bind="click: validateApiToken",
                        ),
                        css_class=hqcrispy.CSS_ACTION_CLASS,
                        data_bind="visible: captureApiToken"
                    ),
                ),
                hqcrispy.FormActions(
                    StrictButton(
                        _('Save'),
                        css_class='btn-primary disable-on-submit',
                        type='submit',
                        data_bind=""
                    )
                )
            )
        )

    @property
    def domain(self):
        return self.instance.domain

    def clean(self):
        cleaned_data = self.cleaned_data
        grouping_method = cleaned_data['selected_grouping_method']
        if grouping_method == GeoConfig.MIN_MAX_GROUPING:
            max_group_size = cleaned_data['max_cases_per_group']
            min_group_size = cleaned_data['min_cases_per_group']
            if not max_group_size:
                raise ValidationError(_("Value for maximum group size required"))
            if not min_group_size:
                raise ValidationError(_("Value for minimum group size required"))
            if min_group_size > max_group_size:
                raise ValidationError(_(
                    "Maximum group size should be greater than or equal to minimum group size"
                ))
        elif grouping_method == GeoConfig.TARGET_SIZE_GROUPING:
            if not cleaned_data['target_group_count']:
                raise ValidationError(_("Value for target group count required"))

        algorithm = cleaned_data.get('selected_disbursement_algorithm')
        token = cleaned_data.get('plaintext_api_token')
        if algorithm == GeoConfig.ROAD_NETWORK_ALGORITHM and not token:
            raise ValidationError(_("Mapbox API token required"))

        return cleaned_data

    def save(self, commit=True):
        if self.cleaned_data.get('plaintext_api_token'):
            self.instance.plaintext_api_token = self.cleaned_data.get('plaintext_api_token')
        return super().save(commit)
