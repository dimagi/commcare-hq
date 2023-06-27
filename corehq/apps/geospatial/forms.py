from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from django.utils.translation import gettext_lazy as _
from django import forms


LOCATION_MODEL = "location_model"
USER_MODEL = "user_model"

LOCATION_SOURCE_OPTIONS = [
    (USER_MODEL, _("Custom user field")),
    (LOCATION_MODEL, _("User's assigned location")),
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
