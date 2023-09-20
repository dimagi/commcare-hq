from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from django.utils.translation import gettext_lazy as _
from django import forms
from corehq.apps.geospatial.models import GeoConfig


LOCATION_SOURCE_OPTIONS = [
    (GeoConfig.CUSTOM_USER_PROPERTY, _("Custom user field")),
    (GeoConfig.ASSIGNED_LOCATION, _("User's assigned location")),
]


class GeospatialConfigForm(forms.ModelForm):

    class Meta:
        model = GeoConfig
        fields = [
            "user_location_property_name",
            "case_location_property_name"
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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


class ConfigureCaseGroupingForm(forms.ModelForm):

    class Meta:
        model = GeoConfig
        fields = [
            "selected_grouping_method",
            "max_cases_per_group",
            "min_cases_per_group",
            "target_group_count",
            "selected_disbursement_algorithm",
        ]

    selected_grouping_method = forms.ChoiceField(
        label=_("Grouping method"),
        help_text=_("Determines which parameter to use for grouping cases"),
        required=False,
        choices=GeoConfig.VALID_GROUPING_METHODS,
    )
    max_cases_per_group = forms.IntegerField(
        label=_("Maximum group size"),
        help_text=_("The minimum number of cases that can be in a group"),
        required=False,
        min_value=1,
    )
    min_cases_per_group = forms.IntegerField(
        label=("Minimum group size"),
        help_text=_("The maximum number of cases that can be in a group"),
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
        # TODO: Uncomment and add documentation link when confluence page for algorithms has been created
        # help_text=format_html_lazy(
        #     _('For more information on these algorithms please look at our '
        #       '<a href="{}" target="_blank">support documentation</a>.'),
        #     ''
        # ),
        choices=GeoConfig.VALID_DISBURSEMENT_ALGORITHMS,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.add_layout(
            crispy.Layout(
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
                    crispy.Field('selected_disbursement_algorithm'),
                ),
                hqcrispy.FormActions(
                    StrictButton(
                        _('Save'),
                        css_class='btn-primary disable-on-submit',
                        type='submit'
                    ),
                )
            )
        )
