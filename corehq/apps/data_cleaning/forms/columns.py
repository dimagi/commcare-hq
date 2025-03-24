import json

from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.data_cleaning.models import (
    DataType,
)
from corehq.apps.data_cleaning.utils.cases import get_case_property_details
from corehq.apps.hqwebapp.widgets import AlpineSelect


class AddColumnForm(forms.Form):
    """
    NOTE: While `AddFilterForm` and `AddColumnForm` share similar properties (`prop_id`, `data_type`)
    the `column_` prefix is used here because both forms will be inserted into the same DOM, resulting
    in the same css ids for each field (generated as `id_<field slug>`). Having multiple elements
    with the same id is invalid HTML. Additionally, this scenario will result in select2s being
    applied to only ONE field.
    """
    column_prop_id = forms.ChoiceField(
        label=gettext_lazy("Case Property"),
        required=False
    )
    column_label = forms.CharField(
        label=gettext_lazy("Label"),
        required=False
    )
    column_data_type = forms.ChoiceField(
        label=gettext_lazy("Data Type"),
        widget=AlpineSelect,
        choices=DataType.CASE_CHOICES,
        required=False
    )

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

        property_details = get_case_property_details(self.session.domain, self.session.identifier)
        self.fields['column_prop_id'].choices = [(None, None)] + [
            (p, p) for p in sorted(property_details.keys())
        ]

        initial_prop_id = self.data.get('column_prop_id')
        is_initial_editable = (
            property_details[initial_prop_id]['is_editable'] if initial_prop_id else True
        )

        offcanvas_selector = "#offcanvas-configure-columns"

        alpine_data_model = {
            "propId": initial_prop_id,
            "dataType": self.data.get(
                'data_type', DataType.CASE_CHOICES[0][0]
            ),
            "casePropertyDetails": property_details,
            "isEditable": is_initial_editable,
        }

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'column_prop_id',
                    x_select2=json.dumps({
                        "placeholder": _("Select a Case Property"),
                        "dropdownParent": offcanvas_selector,
                    }),
                    **({
                        "@select2change": "propId = $event.detail; "
                                          "dataType = casePropertyDetails[$event.detail].data_type; "
                                          "isEditable = casePropertyDetails[$event.detail].is_editable;",
                    })
                ),
                crispy.Div(
                    'column_label',
                    crispy.Div(
                        crispy.Field(
                            'column_data_type',
                            x_model="dataType",
                        ),
                        x_show="isEditable",
                    ),
                    twbscrispy.StrictButton(
                        _("Add Column"),
                        type="submit",
                        css_class="btn-primary",
                    ),
                    x_show="propId",
                ),
                x_data=json.dumps(alpine_data_model),
            )
        )
