import json

from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.data_cleaning.models import (
    DataType,
    FilterMatchType,
)
from corehq.apps.data_cleaning.utils.cases import get_case_property_details


class AddColumnFilterForm(forms.Form):
    prop_id = forms.ChoiceField(
        label=gettext_lazy("Case Property"),
        required=False
    )
    data_type = forms.ChoiceField(
        label=gettext_lazy("Data Type"),
        choices=DataType.CHOICES,
        required=False
    )

    text_match_type = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=FilterMatchType.TEXT_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES,
        required=False
    )
    text_value = forms.CharField(
        label=gettext_lazy("Value"),
        strip=False,
        required=False
    )

    number_match_type = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=FilterMatchType.NUMBER_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES,
        required=False
    )
    number_value = forms.CharField(
        label=gettext_lazy("Value"),
        required=False
    )

    date_match_type = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=FilterMatchType.DATE_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES,
        required=False
    )
    date_value = forms.CharField(
        label=gettext_lazy("Value"),
        required=False
    )

    multi_select_match_type = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=FilterMatchType.MULTI_SELECT_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES,
        required=False
    )
    multi_select_value = forms.CharField(
        label=gettext_lazy("Value"),
        required=False
    )

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

        property_details = get_case_property_details(self.session.domain, self.session.identifier)
        self.fields['prop_id'].choices = [(None, None)] + [
            (p, p) for p in property_details.keys()
        ]

        initial_prop_id = self.fields['prop_id'].initial
        is_initial_editable = (
            property_details[initial_prop_id]['is_editable'] if initial_prop_id else True
        )

        alpine_data_model = {
            "dataType": self.fields['data_type'].initial,
            "propId": initial_prop_id,
            "casePropertyDetails": property_details,
            "isEditable": is_initial_editable,
            "textDataTypes": DataType.FILTER_CATEGORY_DATA_TYPES[
                DataType.FILTER_CATEGORY_TEXT
            ],
            "numberDataTypes": DataType.FILTER_CATEGORY_DATA_TYPES[
                DataType.FILTER_CATEGORY_NUMBER
            ],
            "dateDataTypes": DataType.FILTER_CATEGORY_DATA_TYPES[
                DataType.FILTER_CATEGORY_DATE
            ],
            "multiSelectDataTypes": DataType.FILTER_CATEGORY_DATA_TYPES[
                DataType.FILTER_CATEGORY_MULTI_SELECT
            ],
        }

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'prop_id',
                    x_select2=json.dumps({
                        "placeholder": _("Select a Case Property"),
                    }),
                    **({
                        "@select2change": "propId = $event.detail; "
                                          "dataType = casePropertyDetails[$event.detail].data_type; "
                                          "isEditable = casePropertyDetails[$event.detail].is_editable;",
                    })
                ),
                crispy.Field(
                    'data_type',
                    x_init="dataType = $el.value",
                    x_model="dataType",
                    **({
                        ":disabled": "!isEditable",
                    })
                ),
                crispy.Div(
                    'text_match_type',
                    'text_value',
                    x_show="textDataTypes.includes(dataType)",
                ),
                crispy.Div(
                    'number_match_type',
                    'number_value',
                    x_show="numberDataTypes.includes(dataType)",
                ),
                crispy.Div(
                    'date_match_type',
                    'date_value',
                    x_show="dateDataTypes.includes(dataType)",
                ),
                crispy.Div(
                    'multi_select_match_type',
                    'multi_select_value',
                    x_show="multiSelectDataTypes.includes(dataType)",
                ),
                twbscrispy.StrictButton(
                    _("Add Filter"),
                    type="submit",
                    css_class="btn-primary",
                ),
                x_data=json.dumps(alpine_data_model),
            ),
        )
