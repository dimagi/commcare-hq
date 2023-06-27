from django.core.exceptions import ValidationError
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


class GeospatialConfigForm(forms.Form):

    location_source_option = forms.CharField(
        label=_("Fetch user location data from"),
        widget=forms.Select(choices=LOCATION_SOURCE_OPTIONS),
        required=False,
    )
    custom_user_field_name = forms.CharField(
        label=_("Custom user field name"),
        required=False,
        help_text=_("The the name of the custom user field which stores the user's geo-location data."),
    )
    geo_case_property_name = forms.CharField(
        label=_("Fetch case location data from property"),
        required=True,
        help_text=_("The name of the case property storing the geo-location data of the case."),
    )

    def __init__(self, *args, **kwargs):
        if kwargs.get('config'):
            kwargs['initial'] = self.compute_initial(kwargs.pop('config'))

        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.add_layout(
            crispy.Layout(
                crispy.Fieldset(
                    _("Configure Geospatial Settings"),
                    crispy.Field('location_source_option', data_bind="value: locationSourceOption"),
                    crispy.Div(
                        crispy.Field(
                            'custom_user_field_name',
                            data_bind="value: customUserFieldName"
                        ),
                        data_bind="visible: showCustomField"
                    ),
                    crispy.Field('geo_case_property_name', data_bind="value: geoCasePropertyName"),
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

        if data['location_source_option'] not in GeoConfig.VALID_LOCATION_SOURCES:
            raise ValidationError(_("Invalid location source"))

        if data['location_source_option'] == GeoConfig.CUSTOM_USER_PROPERTY and not data['custom_user_field_name']:
            raise ValidationError(_("Custom user field name required"))

        if not data['geo_case_property_name']:
            raise ValidationError(_("Case property name required"))

        return data

    @staticmethod
    def compute_initial(config):
        return {
            'location_source_option': config.location_data_source,
            'custom_user_field_name': config.user_location_property_name,
            'geo_case_property_name': config.case_location_property_name,
        }
