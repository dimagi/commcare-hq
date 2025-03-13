import datetime
import json

from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.data_cleaning.exceptions import UnsupportedFilterValueException
from corehq.apps.data_cleaning.models import (
    DataType,
    FilterMatchType,
    BulkEditColumnFilter,
)
from corehq.apps.data_cleaning.utils.cases import get_case_property_details

EXCLUDED_FILTERED_PROPERTIES = [
    '@case_type',  # Data cleaning only works with one case type at a time
    '@status',  # the Case Status pinned filter takes care of this
    '@owner_id',  # the Case Owner(s) pinned filter takes care of this
]


class DynamicMultipleChoiceField(forms.MultipleChoiceField):
    def valid_value(self, value):
        """
        Override the parent valid_value method to allow any user-created value
        """
        return True


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
    multi_select_value = DynamicMultipleChoiceField(
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
                crispy.Div(
                    crispy.Field(
                        'data_type',
                        x_model="dataType",
                    ),
                    x_show="isEditable",
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

    def clean_prop_id(self):
        prop_id = self.cleaned_data['prop_id']
        if not prop_id:
            raise forms.ValidationError(_("Please select a case property to filter on."))
        return prop_id

    def clean_data_type(self):
        data_type = self.cleaned_data['data_type']
        return data_type or DataType.TEXT

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get('data_type')
        if data_type is None:
            self.add_error('data_type', _("Please specify a data type."))
            return cleaned_data

        category = self.get_data_type_category(data_type)
        clean_fn = {
            DataType.FILTER_CATEGORY_TEXT: lambda x: self._clean_text_filter(x),
            DataType.FILTER_CATEGORY_NUMBER: lambda x: self._clean_number_filter(x),
            DataType.FILTER_CATEGORY_DATE: lambda x: self._clean_date_filter(x),
            DataType.FILTER_CATEGORY_MULTI_SELECT: lambda x: self._clean_multi_select_filter(x),
        }.get(category)
        if not clean_fn:
            # should never be reached unless a user manually edits the form
            self.add_error('data_type', _("Unrecognized data type."))
            return cleaned_data

        return clean_fn(cleaned_data)

    @staticmethod
    def get_data_type_category(data_type):
        for category, valid_data_types in DataType.FILTER_CATEGORY_DATA_TYPES.items():
            if data_type in valid_data_types:
                return category

    def _clean_text_filter(self, cleaned_data):
        match_type = self._clean_required_match_type('text_match_type', cleaned_data)
        value = self._clean_value_for_match_type('text_value', cleaned_data, match_type)
        if value is not None:
            try:
                BulkEditColumnFilter.get_quoted_value(value)
            except UnsupportedFilterValueException:
                self.add_error('text_value', _("This value cannot contain both single quotes (') "
                                               "and double quotes (\") at the same time."))
        return self._save_to_cleaned_data(cleaned_data, match_type, value)

    def _clean_number_filter(self, cleaned_data):
        match_type = self._clean_required_match_type('number_match_type', cleaned_data)
        value = self._clean_value_for_match_type('number_value', cleaned_data, match_type)
        if value:
            try:
                # we currently do not differentiate between integer or decimal
                float(value)
            except ValueError:
                self.add_error('number_value', _("Not a valid number."))
        return self._save_to_cleaned_data(cleaned_data, match_type, value)

    def _clean_date_filter(self, cleaned_data):
        data_type = cleaned_data['data_type']
        match_type = self._clean_required_match_type('date_match_type', cleaned_data)
        value_field_name = {
            DataType.DATE: 'date_value',
            DataType.DATETIME: 'datetime_value',
        }.get(data_type)
        if not value_field_name:
            # we should never arrive here, but just in case
            self.add_error('data_type', _("Unknown date type."))
            return cleaned_data
        value = self._clean_value_for_match_type(value_field_name, cleaned_data, match_type)
        valid_format, error_message = {
            DataType.DATE: (
                "%Y-%m-%d", _("Date format should be 'YYYY-MM-DD'")
            ),
            DataType.DATETIME: (
                "%Y-%m-%d %H:%M:%S", _("Date and Time format should be 'YYYY-MM-DD HH:MM:SS', "
                                       "where the hour is the 24-hour format, 00 to 23.")
            ),
        }[data_type]
        if value is not None:
            try:
                datetime.datetime.strptime(value, valid_format)
            except ValueError:
                self.add_error(value_field_name, error_message)
        return self._save_to_cleaned_data(cleaned_data, match_type, value)

    def _clean_required_match_type(self, match_type_field_name, cleaned_data):
        match_type = cleaned_data.get(match_type_field_name)
        if not match_type:
            self.add_error(match_type_field_name, _("Please select a match type."))
        return match_type

    def _clean_multi_select_filter(self, cleaned_data):
        match_type = self._clean_required_match_type('multi_select_match_type', cleaned_data)
        value = self._clean_value_for_match_type('multi_select_value', cleaned_data, match_type)
        if value is not None:
            value = " ".join(value)
        return self._save_to_cleaned_data(cleaned_data, match_type, value)

    def _clean_value_for_match_type(self, value_field_name, cleaned_data, match_type):
        is_value_required = match_type not in dict(FilterMatchType.ALL_DATA_TYPES_CHOICES)
        value = cleaned_data.get(value_field_name)
        if is_value_required and not value:
            self.add_error(value_field_name, _("Please provide a value or use the "
                                               "'empty' or 'missing' match types."))
        return value if is_value_required else None

    def _save_to_cleaned_data(self, cleaned_data, match_type, value):
        data_type = cleaned_data['data_type']
        cleaned_data['match_type'] = match_type
        cleaned_data['value'] = value
        # one last check
        if not BulkEditColumnFilter.is_data_and_match_type_valid(
            match_type, data_type
        ):
            self.add_error('data_type', _("Data type '{}' cannot have match type '{}'.").format(
                data_type, match_type
            ))
        return cleaned_data
