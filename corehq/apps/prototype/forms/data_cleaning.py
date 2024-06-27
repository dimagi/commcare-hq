import json

from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.prototype.models.data_cleaning.actions import CleaningActionType
from corehq.apps.prototype.models.data_cleaning.columns import EditableColumn
from corehq.apps.prototype.models.data_cleaning.filters import ColumnMatchType, ColumnFilter


class AddColumnFilterForm(forms.Form):
    slug = forms.ChoiceField(
        label=gettext_lazy("Column"),
        choices=(),
    )
    match = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=ColumnMatchType.OPTIONS,
    )
    value = forms.CharField(
        label=gettext_lazy("Value"),
    )

    def __init__(self, table_config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].choices = [
            (c[0], c[1].verbose_name)
            for c in table_config.available_columns
        ]

        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            'slug',
            'match',
            'value',
            twbscrispy.StrictButton(
                _("Add Filter"),
                type="submit",
                css_class="btn-primary",
            ),
        )

    def add_filter(self, request):
        ColumnFilter.add_filter(
            request,
            self.cleaned_data['slug'],
            self.cleaned_data['match'],
            self.cleaned_data['value'],
        )


class CleanColumnDataForm(forms.Form):
    slug = forms.ChoiceField(
        label=gettext_lazy("Select a property to clean:"),
        choices=(),
        required=False,
    )
    action = forms.ChoiceField(
        label=gettext_lazy("Data cleaning action:"),
        choices=CleaningActionType.OPTIONS,
        required=False,
    )
    find_string = forms.CharField(
        label=gettext_lazy("Find:"),
        required=False,
    )
    replace_string = forms.CharField(
        label=gettext_lazy("Replace with:"),
        required=False,
    )
    replace_all_string = forms.CharField(
        label=gettext_lazy("Replace existing value with:"),
        required=False,
    )

    def __init__(self, table_config, data_store, *args, **kwargs):
        self.data_store = data_store
        super().__init__(*args, **kwargs)

        self.fields['slug'].choices = [
            ('', _("Select a property...")),
        ] + table_config.get_editable_column_options()

        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'slug',
                    x_init="slug = $el.value",
                    x_model="slug",
                ),
                crispy.Field(
                    'action',
                    x_init="action = $el.value",
                    x_model="action",
                ),
                crispy.Div(
                    crispy.Div(
                        crispy.Div(
                            'find_string',
                            'replace_string',
                        ),
                        css_class="card-body",
                    ),
                    x_show="findActions.includes(action)",
                    css_class="card mb-3",
                ),
                crispy.Div(
                    crispy.Div(
                        crispy.Div(
                            'replace_all_string',
                        ),
                        css_class="card-body",
                    ),
                    x_show="replaceAllActions.includes(action)",
                    css_class="card mb-3",
                ),
                crispy.Div(
                    twbscrispy.StrictButton(
                        _("Preview Changes"),
                        type="submit",
                        data_bs_dismiss="offcanvas",
                        css_class="btn btn-primary",
                        **({':disabled': '!slug || !action'})
                    ),
                    css_class="py-3 d-lex flex-row-reverse"
                ),
                x_data=json.dumps({
                    "slug": self.fields['slug'].initial,
                    "action": self.fields["action"].initial,
                    "findActions": CleaningActionType.FIND_ACTIONS,
                    "replaceAllActions": CleaningActionType.REPLACE_ALL_ACTIONS,
                }),
            ),
        )

    def clean(self):
        action = self.cleaned_data['action']
        if action in CleaningActionType.FIND_ACTIONS:
            if not self.cleaned_data['find_string']:
                self.add_error('find_string', _("Please include a value to find and replace."))

    def apply_actions_to_data(self):
        action_map = {
            CleaningActionType.REPLACE: self._replace,
            CleaningActionType.FIND_REPLACE: self._find_and_replace,
            CleaningActionType.STRIP: self._strip_whitespace,
        }
        action_fn = action_map[self.cleaned_data['action']]
        action_fn()

    def _replace(self):
        rows = self.data_store.get()
        slug = self.cleaned_data['slug']
        replace_all_string = self.cleaned_data['replace_all_string']
        edited_slug = EditableColumn.get_edited_slug(slug)
        for row in rows:
            if not row["selected"]:
                continue
            row[edited_slug] = replace_all_string
        self.data_store.set(rows)

    def _find_and_replace(self):
        rows = self.data_store.get()
        slug = self.cleaned_data['slug']
        find_string = self.cleaned_data['find_string']
        replace_string = self.cleaned_data['replace_string']
        edited_slug = EditableColumn.get_edited_slug(slug)
        for row in rows:
            if not row["selected"]:
                continue
            column = row[slug]
            if find_string in column:
                row[edited_slug] = column.replace(find_string, replace_string)
        self.data_store.set(rows)

    def _strip_whitespace(self):
        # todo
        pass
