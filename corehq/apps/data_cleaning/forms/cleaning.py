import json
import re

from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.data_cleaning.models import (
    BulkEditChange,
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
            "replaceActions": [EditActionType.REPLACE],
            "findActions": [EditActionType.FIND_REPLACE],
            "copyActions": [EditActionType.COPY_REPLACE],
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
                            'replace_all_string',
                            css_class="card-body",
                        ),
                        x_show="replaceActions.includes(cleanAction)",
                        css_class="card mb-3",
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
                    crispy.Div(
                        crispy.Div(
                            crispy.Field(
                                'copy_from_prop_id',
                                x_select2=json.dumps({
                                    "placeholder": _("Select a case property..."),
                                    "dropdownParent": offcanvas_selector,
                                }),
                            ),
                            css_class="card-body",
                        ),
                        x_show="copyActions.includes(cleanAction)",
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

    def clean(self):
        cleaned_data = super().clean()
        clean_action = cleaned_data.get("clean_action")

        if clean_action == EditActionType.REPLACE:
            if not cleaned_data.get("replace_all_string"):
                self.add_error(
                    "replace_all_string",
                    _(
                        "Please specify a value you would like to replace the existing property value with."
                    ),
                )
                return cleaned_data

        if clean_action == EditActionType.FIND_REPLACE:
            # note: allow empty replace_string

            find_string = cleaned_data.get("find_string")
            if not find_string:
                self.add_error(
                    "find_string", _("Please specify the value you would like to find.")
                )
                return cleaned_data

            use_regex = cleaned_data.get("use_regex")
            if use_regex:
                try:
                    re.compile(find_string)
                except re.error:
                    self.add_error("find_string", _("Not a valid regular expression."))
                    return cleaned_data

        if clean_action == EditActionType.COPY_REPLACE:
            copy_from_prop_id = cleaned_data.get("copy_from_prop_id")
            if not copy_from_prop_id:
                self.add_error(
                    "copy_from_prop_id",
                    _("Please select a property to copy from."),
                )
                return cleaned_data
            if copy_from_prop_id == cleaned_data.get("clean_prop_id"):
                self.add_error(
                    "copy_from_prop_id",
                    _("You cannot copy from the same property."),
                )
                return cleaned_data

        return cleaned_data

    def create_bulk_edit_change(self):
        prop_id = self.cleaned_data["clean_prop_id"]
        action_type = self.cleaned_data["clean_action"]
        change_kwargs = {
            EditActionType.REPLACE: {
                "replace_string": self.cleaned_data["replace_all_string"],
            },
            EditActionType.FIND_REPLACE: {
                "find_string": self.cleaned_data["find_string"],
                "replace_string": self.cleaned_data["replace_string"],
                "use_regex": self.cleaned_data["use_regex"],
            },
            EditActionType.COPY_REPLACE: {
                "copy_from_prop_id": self.cleaned_data["copy_from_prop_id"],
            },
        }.get(action_type, {})
        return BulkEditChange.objects.create(
            session=self.session,
            prop_id=prop_id,
            action_type=action_type,
            **change_kwargs,
        )

    def dict_lookup(self):
        action_type = self.cleaned_data['clean_action']
        change_kwargs = {
            EditActionType.REPLACE: {
                "replace_string": self.cleaned_data["replace_all_string"],
            },
            EditActionType.FIND_REPLACE: {
                "find_string": self.cleaned_data["find_string"],
                "replace_string": self.cleaned_data["replace_string"],
                "use_regex": self.cleaned_data["use_regex"],
            },
            EditActionType.COPY_REPLACE: {
                "copy_from_prop_id": self.cleaned_data["copy_from_prop_id"],
            },
        }.get(action_type, {})
        return change_kwargs

    def conditional(self):
        action_type = self.cleaned_data['clean_action']
        change_kwargs = None
        if action_type == EditActionType.REPLACE:
            change_kwargs = {'replace_string': self.cleaned_data['replace_all_string']}
        elif action_type == EditActionType.FIND_REPLACE:
            change_kwargs = {
                'find_string': self.cleaned_data['find_string'],
                'replace_string': self.cleaned_data['replace_string'],
                'use_regex': self.cleaned_data['use_regex'],
            }
        elif action_type == EditActionType.COPY_REPLACE:
            change_kwargs = {'copy_from_prop_id': self.cleaned_data['copy_from_prop_id']}

        return change_kwargs


def time_lookup(operation_name):
    import timeit
    from corehq.apps.data_cleaning.models import BulkEditSession

    session = BulkEditSession.objects.first()

    form = CleanSelectedRecordsForm(session, data={
        'clean_action': EditActionType.FIND_REPLACE,
        'find_string': 'some_string',
        'replace_string': 'new_string',
    })
    form.full_clean()
    operation = getattr(form, operation_name)

    def timed_code():
        garbage_value = 0
        change_kwargs = operation()
        if change_kwargs:
            garbage_value = 9

        return garbage_value

    elapsed = timeit.timeit(timed_code)
    print(f'{operation.__name__} took: {elapsed}')


def time_dict_lookup():
    time_lookup('dict_lookup')


def time_conditional_lookup():
    time_lookup('conditional')
