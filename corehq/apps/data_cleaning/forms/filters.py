import json

from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.data_cleaning.models import (
    DataType,
    FilterMatchType,
)
from corehq.apps.data_cleaning.utils.cases import get_case_property_details

EXCLUDED_FILTERED_PROPERTIES = [
    '@case_type',  # Data cleaning only works with one case type at a time
    '@status',  # the Case Status pinned filter takes care of this
    '@owner_id',  # the Case Owner(s) pinned filter takes care of this
]


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
    datetime_value = forms.CharField(
        label=gettext_lazy("Value"),
        required=False
    )

    multi_select_match_type = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=FilterMatchType.MULTI_SELECT_CHOICES + FilterMatchType.ALL_DATA_TYPES_CHOICES,
        required=False
    )
    multi_select_value = forms.MultipleChoiceField(
        label=gettext_lazy("Value"),
        required=False
    )

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

        property_details = get_case_property_details(self.session.domain, self.session.identifier)
        self.fields['prop_id'].choices = [(None, None)] + [
            (p, p) for p in sorted(property_details.keys()) if p not in EXCLUDED_FILTERED_PROPERTIES
        ]

        initial_prop_id = self._get_initial_value('prop_id')
        is_initial_editable = (
            property_details[initial_prop_id]['is_editable'] if initial_prop_id else True
        )

        offcanvas_selector = "#offcanvas-filter"

        alpine_data_model = {
            "dataType": self._get_initial_value(
                'data_type', DataType.CASE_CHOICES[0][0]
            ),
            "propId": initial_prop_id,
            "casePropertyDetails": property_details,
            "isEditable": is_initial_editable,
            "datetimeTypes": [DataType.DATETIME],
            "dateTypes": [DataType.DATE],
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
            "textMatchType": self._get_initial_value(
                'text_match_type', FilterMatchType.TEXT_CHOICES[0][0]
            ),
            "numberMatchType": self._get_initial_value(
                'number_match_type', FilterMatchType.NUMBER_CHOICES[0][0]
            ),
            "dateMatchType": self._get_initial_value(
                'date_match_type', FilterMatchType.DATE_CHOICES[0][0]
            ),
            "multiSelectMatchType": self._get_initial_value(
                'multi_select_match_type', FilterMatchType.MULTI_SELECT_CHOICES[0][0]
            ),
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
                        "dropdownParent": offcanvas_selector,
                    }),
                    **({
                        "@select2change": "propId = $event.detail; "
                                          "dataType = casePropertyDetails[$event.detail].data_type; "
                                          "isEditable = casePropertyDetails[$event.detail].is_editable;",
                    })
                ),
                crispy.Field(
                    'data_type',
                    x_model="dataType",
                    **({
                        ":disabled": "!isEditable",
                    })
                ),
                crispy.Div(
                    crispy.Field(
                        'text_match_type',
                        x_select2=json.dumps({
                            "dropdownParent": offcanvas_selector,
                        }),
                        **({
                            "@select2change": "textMatchType = $event.detail",
                        })
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
                        x_select2=json.dumps({
                            "dropdownParent": offcanvas_selector,
                        }),
                        **({
                            "@select2change": "numberMatchType = $event.detail",
                        })
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
                        x_select2=json.dumps({
                            "dropdownParent": offcanvas_selector,
                        }),
                        **({
                            "@select2change": "dateMatchType = $event.detail",
                        })
                    ),
                    crispy.Div(
                        twbscrispy.AppendedText(
                            'date_value',
                            mark_safe(  # nosec: no user input
                                '<i class="fa-solid fa-calendar-days"></i>'
                            ),
                            x_datepicker=json.dumps({
                                "container": offcanvas_selector,
                                "useInputGroup": True,
                            }),
                        ),
                        x_show="!matchTypesWithNoValue.includes(dateMatchType) "
                               "&& dateTypes.includes(dataType)"
                    ),
                    crispy.Div(
                        twbscrispy.AppendedText(
                            'datetime_value',
                            mark_safe(  # nosec: no user input
                                '<i class="fcc fcc-fd-datetime"></i>'
                            ),
                            x_datepicker=json.dumps({
                                "datetime": True,
                                "container": offcanvas_selector,
                                "useInputGroup": True,
                            }),
                        ),
                        x_show="!matchTypesWithNoValue.includes(dateMatchType) "
                               "&& datetimeTypes.includes(dataType)"
                    ),
                    x_show="dateDataTypes.includes(dataType)",
                ),
                crispy.Div(
                    crispy.Field(
                        'multi_select_match_type',
                        x_select2=json.dumps({
                            "dropdownParent": offcanvas_selector,
                        }),
                        **({
                            "@select2change": "multiSelectMatchType = $event.detail",
                        })
                    ),
                    crispy.Div(
                        crispy.Field(
                            'multi_select_value',
                            x_init="$watch("
                                   "  'propId',"
                                   "  value => $dispatch('updateAddFilterPropId', { value: value })"
                                   ")",
                            x_dynamic_options_select2=json.dumps({
                                "details": property_details,
                                "eventName": 'updateAddFilterPropId',
                                "initialPropId": initial_prop_id,
                            }),
                        ),
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

    def _get_initial_value(self, field_name, default_value=None):
        return self.data.get(
            field_name, self.fields[field_name].initial or default_value
        )
