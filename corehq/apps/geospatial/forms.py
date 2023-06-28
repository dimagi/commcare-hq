from django.core.exceptions import ValidationError
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from django.utils.translation import gettext_lazy as _
from django import forms
from django.forms.models import model_to_dict
from corehq.apps.geospatial.models import GeoConfig


LOCATION_SOURCE_OPTIONS = [
    (GeoConfig.CUSTOM_USER_PROPERTY, _("Custom user field")),
    (GeoConfig.ASSIGNED_LOCATION, _("User's assigned location")),
]


class GeospatialConfigForm(forms.ModelForm):

    class Meta:
        model = GeoConfig
        fields = [
            "location_data_source",
            "user_location_property_name",
            "case_location_property_name"
        ]

    location_data_source = forms.CharField(
        label=_("Fetch user location data from"),
        widget=forms.Select(choices=LOCATION_SOURCE_OPTIONS),
        required=False,
    )
    user_location_property_name = forms.CharField(
        label=_("Custom user field name"),
        required=False,
        help_text=_("The name of the user field which stores the users' geo-location data."),
    )
    case_location_property_name = forms.CharField(
        label=_("Fetch case location data from property"),
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
                    crispy.Field('location_data_source', data_bind="value: locationSourceOption"),
                    crispy.Div(
                        crispy.Field(
                            'user_location_property_name',
                            data_bind="value: customUserFieldName"
                        ),
                        data_bind="visible: showCustomField"
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

    def clean(self):
        data = self.cleaned_data

        if data['location_data_source'] not in GeoConfig.VALID_LOCATION_SOURCES:
            raise ValidationError(_("Invalid location source"))

        if (
            data['location_data_source'] == GeoConfig.CUSTOM_USER_PROPERTY and  # noqa: W504
            not data['user_location_property_name']
        ):
            raise ValidationError(_("Custom user field name required"))

        if data['location_data_source'] == GeoConfig.ASSIGNED_LOCATION:
            # Reset incase user changed it before changing location_data_source
            data['user_location_property_name'] = self.instance.user_location_property_name

        if not data['case_location_property_name']:
            raise ValidationError(_("Case property name required"))

        return data
