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


class AddColumnFilterForm(forms.Form):
    prop_id = forms.ChoiceField(
        label=gettext_lazy("Case Property"),
        choices=(),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Div(
                'prop_id',
                crispy.Field(
                    'data_type',
                    x_init="dataType = $el.value",
                    x_model="dataType",
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
                x_data=json.dumps({
                    "dataType": self.fields['data_type'].initial,
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
                }),
            ),
        )
