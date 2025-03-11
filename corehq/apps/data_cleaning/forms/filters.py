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
        choices=DataType.CASE_CHOICES,
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
        required=False,
        widget=forms.NumberInput,
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
            "textMatchType": self.fields['text_match_type'].initial,
            "numberMatchType": self.fields['number_match_type'].initial,
            "dateMatchType": self.fields['date_match_type'].initial,
            "multiSelectMatchType": self.fields['multi_select_match_type'].initial,
            "matchTypesWithNoValue": [
                f[0] for f in FilterMatchType.ALL_DATA_TYPES_CHOICES
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
                        "dropdownParent": "#offcanvas-filter",
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
                    crispy.Field(
                        'text_match_type',
                        x_init="textMatchType = $el.value",
                        x_model="textMatchType",
                    ),
                    crispy.Div(
                        crispy.Field(
                            'text_value',
                            autocomplete="off",
                        ),
                        x_show="!matchTypesWithNoValue.includes(textMatchType)"
                    ),
                    x_show="textDataTypes.includes(dataType)",
                ),
                crispy.Div(
                    crispy.Field(
                        'number_match_type',
                        x_init="numberMatchType = $el.value",
                        x_model="numberMatchType",
                    ),
                    crispy.Div(
                        crispy.Field(
                            'number_value',
                            autocomplete="off",
                        ),
                        x_show="!matchTypesWithNoValue.includes(numberMatchType)"
                    ),
                    x_show="numberDataTypes.includes(dataType)",
                ),
                crispy.Div(
                    crispy.Field(
                        'date_match_type',
                        x_init="dateMatchType = $el.value",
                        x_model="dateMatchType",
                    ),
                    crispy.Div(
                        'date_value',
                        x_show="!matchTypesWithNoValue.includes(dateMatchType)"
                    ),
                    x_show="dateDataTypes.includes(dataType)",
                ),
                crispy.Div(
                    crispy.Field(
                        'multi_select_match_type',
                        x_init="multiSelectMatchType = $el.value",
                        x_model="multiSelectMatchType",
                    ),
                    crispy.Div(
                        'multi_select_value',
                        x_show="!matchTypesWithNoValue.includes(multiSelectMatchType)",

                    ),
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
