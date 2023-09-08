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
