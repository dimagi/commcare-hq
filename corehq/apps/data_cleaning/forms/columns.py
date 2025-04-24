import json

from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.data_cleaning.models import (
    DataType,
    BulkEditColumn,
)
from corehq.apps.data_cleaning.utils.cases import (
    get_case_property_details,
    get_system_property_data_type,
)
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
        self.existing_columns = self.session.columns.values_list('prop_id', flat=True)
        self.fields['column_prop_id'].choices = [(None, None)] + [
            (p, p) for p in sorted(property_details.keys()) if p not in self.existing_columns
        ]

        initial_prop_id = self.data.get('column_prop_id')
        is_initial_editable = (
            property_details[initial_prop_id]['is_editable'] if initial_prop_id else True
        )
        default_label = (
            property_details[initial_prop_id]['label'] if initial_prop_id else ""
        )
        initial_label = self.data.get('column_label', default_label)

        offcanvas_selector = "#offcanvas-configure-columns"

        alpine_data_model = {
            "propId": initial_prop_id,
            "dataType": self.data.get(
                'data_type', DataType.CASE_CHOICES[0][0]
            ),
            'label': initial_label,
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
                                          "label = casePropertyDetails[$event.detail].label; "
                                          "isEditable = casePropertyDetails[$event.detail].is_editable;",
                    })
                ),
                crispy.Div(
                    crispy.Field(
                        'column_label',
                        x_model="label",
                    ),
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

    def clean_column_label(self):
        column_label = self.cleaned_data.get('column_label')
        if not column_label:
            raise forms.ValidationError(_("Please specify a label for the column."))
        return column_label

    def clean_column_data_type(self):
        data_type = self.cleaned_data.get('column_data_type')
        if not data_type:
            raise forms.ValidationError(_("Please specify a data type."))
        return data_type

    def clean_column_prop_id(self):
        prop_id = self.cleaned_data.get('column_prop_id')
        if not prop_id:
            raise forms.ValidationError(_("Please specify a case property."))
        if prop_id in self.existing_columns:
            raise forms.ValidationError(_("This case property is already a column."))
        return prop_id

    def clean(self):
        cleaned_data = super().clean()
        data_type = cleaned_data.get('column_data_type')
        prop_id = cleaned_data.get('column_prop_id')
        is_system_property = BulkEditColumn.is_system_property(prop_id)
        if is_system_property:
            expected_data_type = get_system_property_data_type(prop_id)
            if expected_data_type != data_type:
                self.add_error(
                    'column_data_type',
                    _("Incorrect data type for '{prop_id}', should be '{expected_data_type}'").format(
                        prop_id=prop_id,
                        expected_data_type=expected_data_type
                    )
                )
        return cleaned_data

    def add_column(self):
        self.session.add_column(
            self.cleaned_data['column_prop_id'],
            self.cleaned_data['column_label'],
            self.cleaned_data['column_data_type']
        )
