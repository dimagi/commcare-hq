from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from django.utils.translation import gettext_lazy as _
from django import forms
from corehq.apps.geospatial.models import GeoConfig
from corehq.apps.data_dictionary.util import get_gps_properties_all_case_types
from .const import GEO_POINT_CASE_PROPERTY
from .utils import get_geo_case_property

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
    case_location_property_name = forms.ChoiceField(
        label=_("Fetch case location data from property"),
        choices=(),
        required=True,
        help_text=_("The name of the case property storing the geo-location data of your cases."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['case_location_property_name'].choices = self._get_gps_prop_choices()
        self.helper = hqcrispy.HQFormHelper()
        self.helper.add_layout(
            crispy.Layout(
                crispy.Fieldset(
                    _("Configure Geospatial Settings"),
                    crispy.Div(
                        crispy.HTML('%s' % _(
                            "The custom case property has been deprecated in the Data Dictionary. "
                            "Please consider switching this to another property.")
                        ),
                        css_class='alert alert-warning',
                        data_bind="visible: isCasePropDeprecated"
                    ),
                    crispy.Field(
                        'user_location_property_name',
                        data_bind="value: customUserFieldName"
                    ),
                    crispy.Field('case_location_property_name', data_bind="value: geoCasePropertyName"),
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

    def _get_gps_prop_choices(self):
        gps_props = get_gps_properties_all_case_types(self.instance.domain)

        # The selected geo case property may be deprecated, so we
        # should fetch it to ensure it is in the final list
        gps_props.add(get_geo_case_property(self.instance.domain))
        return (
            tuple((prop_name, prop_name) for prop_name in gps_props)
            if gps_props
            else [(GEO_POINT_CASE_PROPERTY, GEO_POINT_CASE_PROPERTY)]
        )
