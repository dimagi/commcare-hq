import json

from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.data_cleaning.models import (
    EditActionType,
)
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import AlpineSelect, BootstrapSwitchInput


class CleanSelectedRecordsForm(forms.Form):
    """
    NOTE: While the related forms for this feature share similar properties (`prop_id`)
    the `clean_` prefix is used here because all forms will be inserted into the same DOM, resulting
    in the same css ids for each field (generated as `id_<field slug>`). Having multiple elements
    with the same id is invalid HTML. Additionally, this scenario will result in select2s being
    applied to only ONE field.
    """
    clean_prop_id = forms.ChoiceField(
        label=gettext_lazy("Select a property to clean"),
        required=False,
        help_text=gettext_lazy(
            "Choices are editable case properties that are "
            "currently visible in the table."
        ),
    )
    clean_action = forms.ChoiceField(
        label=gettext_lazy("Data cleaning action"),
        widget=AlpineSelect,
        choices=EditActionType.CHOICES,
        required=False
    )
    find_string = forms.CharField(
        label=gettext_lazy("Find:"),
        strip=False,
        required=False,
    )
    use_regex = forms.CharField(
        label="",
        required=False,
        widget=BootstrapSwitchInput(
            inline_label=gettext_lazy(
                "Use regular expression"
            ),
        ),
    )
    replace_string = forms.CharField(
        label=gettext_lazy("Replace with:"),
        strip=False,
        required=False,
    )
    replace_all_string = forms.CharField(
        label=gettext_lazy("Replace existing value with:"),
        strip=False,
        required=False,
    )
    copy_from_prop_id = forms.ChoiceField(
        label=gettext_lazy("Copy from property:"),
        choices=(),
        required=False,
        help_text=gettext_lazy(
            "The value from this property will replace the "
            "value from the selected property at the top."
        ),
    )

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

        self.editable_columns = self.session.columns.filter(is_system=False)
        self.is_form_visible = self.editable_columns.count() > 0

        property_choices = [(None, None)] + [
            (column.prop_id, column.choice_label) for column in self.editable_columns
        ]
        self.fields['clean_prop_id'].choices = property_choices
        self.fields['copy_from_prop_id'].choices = property_choices

        initial_prop_id = self.data.get('clean_prop_id')

        offcanvas_selector = "#offcanvas-bulk-changes"

        alpine_data_model = {
            "propId": initial_prop_id,
            "cleanAction": self.data.get('clean_action', EditActionType.CHOICES[0][0]),
            "findActions": [EditActionType.FIND_REPLACE],
        }

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'clean_prop_id',
                    x_select2=json.dumps({
                        "placeholder": _("Select a case property..."),
                        "dropdownParent": offcanvas_selector,
                    }),
                    **({
                        "@select2change": "propId = $event.detail;",
                    })
                ),
                crispy.Div(
                    crispy.Field(
                        'clean_action',
                        x_select2=json.dumps({
                            "placeholder": _("Select a cleaning action..."),
                            "dropdownParent": offcanvas_selector,
                        }),
                        **({
                            "@select2change": "cleanAction = $event.detail;",
                        })
                    ),
                    crispy.Div(
                        crispy.Div(
                            'find_string',
                            hqcrispy.CheckboxField('use_regex'),
                            'replace_string',
                            css_class="card-body",
                        ),
                        x_show="findActions.includes(cleanAction)",
                        css_class="card mb-3",
                    ),
                    twbscrispy.StrictButton(
                        _("Preview Changes"),
                        type="submit",
                        css_class="btn-primary",
                    ),
                    x_show="propId",
                ),
                x_data=json.dumps(alpine_data_model),
            )
        )
