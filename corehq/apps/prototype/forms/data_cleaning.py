import json
import re

from django import forms
from django.utils.translation import gettext as _, gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapSwitchInput
from corehq.apps.prototype.models.data_cleaning.actions import CleaningActionType
from corehq.apps.prototype.models.data_cleaning.columns import EditableColumn
from corehq.apps.prototype.models.data_cleaning.filters import ColumnMatchType


class AddColumnFilterForm(forms.Form):
    slug = forms.ChoiceField(
        label=gettext_lazy("Column"),
        choices=(),
        required=False
    )
    match = forms.ChoiceField(
        label=gettext_lazy("Match Type"),
        choices=ColumnMatchType.OPTIONS,
        required=False
    )
    use_regex = forms.BooleanField(
        label="",
        required=False,
        widget=BootstrapSwitchInput(
            inline_label=gettext_lazy(
                "Use regular expression"
            ),
        ),
    )
    value = forms.CharField(
        label=gettext_lazy("Value"),
        strip=False,
        required=False
    )

    def __init__(self, column_manager, *args, **kwargs):
        self.column_manager = column_manager
        super().__init__(*args, **kwargs)
        self.fields['slug'].choices = [
            (c[0], c[1].verbose_name)
            for c in self.column_manager.get_available_columns()
        ]

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Div(
                'slug',
                crispy.Field(
                    'match',
                    x_init="match = $el.value",
                    x_model="match",
                ),
                crispy.Div(
                    'value',
                    x_show="!noValueMatch.includes(match)",
                ),
                crispy.Div(
                    hqcrispy.CheckboxField('use_regex'),
                    x_show="regexMatches.includes(match)",
                ),
                twbscrispy.StrictButton(
                    _("Add Filter"),
                    type="submit",
                    css_class="btn-primary htmx-loading",
                ),
                x_data=json.dumps({
                    "match": self.fields['match'].initial,
                    "noValueMatch": ColumnMatchType.NO_VALUE_MATCHES,
                    "regexMatches": ColumnMatchType.REGEX_MATCHES,
                }),
            ),
        )

    def clean(self):
        match = self.cleaned_data['match']
        value = self.cleaned_data['value']
        if match in ColumnMatchType.REGEX_MATCHES:
            if self.cleaned_data['use_regex']:
                try:
                    re.compile(value)
                except re.error:
                    self.add_error('value', _("Not a valid regular expression"))
        if match not in ColumnMatchType.NO_VALUE_MATCHES and not value:
            if match in ColumnMatchType.NEGATIVE_STRING_MATCHES:
                self.add_error('value', _('Please provide a value or use Match Type '
                                          '"is not empty" or "is not null"'))
            else:
                self.add_error('value', _('Please provide a value or use Match Type '
                                          '"is empty" or "is null"'))

    def add_filter(self):
        use_regex = self.cleaned_data['use_regex']
        match = self.cleaned_data['match']
        if match not in ColumnMatchType.REGEX_MATCHES:
            use_regex = False
        self.column_manager.add_filter(
            self.cleaned_data['slug'],
            match,
            self.cleaned_data['value'],
            use_regex,
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
    copy_slug = forms.ChoiceField(
        label=gettext_lazy("Copy from property:"),
        choices=(),
        required=False,
        help_text=gettext_lazy(
            "The value from this property will replace the "
            "value from the selected property at the top."
        ),
    )

    def __init__(self, column_manager, data_store, *args, **kwargs):
        self.column_manager = column_manager
        self.data_store = data_store
        self.filtered_ids = []
        if self.column_manager.has_filters():
            # todo simplify
            self.filtered_ids = self.column_manager.filtered_record_ids
        super().__init__(*args, **kwargs)

        self.fields['slug'].choices = [
            ('', _("Select a property...")),
        ] + column_manager.get_editable_column_options()

        self.fields['copy_slug'].choices = column_manager.get_editable_column_options()

        self.helper = FormHelper()
        self.helper.form_tag = False
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
                            hqcrispy.CheckboxField('use_regex'),
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
                    crispy.Div(
                        crispy.Div(
                            'copy_slug',
                        ),
                        css_class="card-body",
                    ),
                    x_show="copyActions.includes(action)",
                    css_class="card mb-3",
                ),
                crispy.Div(
                    twbscrispy.StrictButton(
                        _("Preview Changes"),
                        type="submit",
                        css_class="btn btn-primary htmx-loading",
                        **({':disabled': '!slug || !action'})
                    ),
                    twbscrispy.StrictButton(
                        _("Close"),
                        type="button",
                        data_bs_dismiss="offcanvas",
                        css_class="btn btn-outline-primary",
                    ),
                    css_class="py-3 d-lex flex-row-reverse"
                ),
                x_data=json.dumps({
                    "slug": self.fields['slug'].initial,
                    "action": self.fields["action"].initial,
                    "findActions": CleaningActionType.FIND_ACTIONS,
                    "replaceAllActions": CleaningActionType.REPLACE_ALL_ACTIONS,
                    "copyActions": CleaningActionType.COPY_ACTIONS,
                }),
            ),
        )

    def clean(self):
        action = self.cleaned_data['action']
        if action in CleaningActionType.FIND_ACTIONS:
            if self.cleaned_data['use_regex']:
                try:
                    re.compile(self.cleaned_data['find_string'])
                except re.error:
                    self.add_error('find_string', _("Not a valid regular expression"))

        if action in CleaningActionType.COPY_ACTIONS:
            if self.cleaned_data['slug'] == self.cleaned_data['copy_slug']:
                self.add_error('copy_slug', _("Please select a different property."))

    def apply_actions_to_data(self):
        action_map = {
            CleaningActionType.REPLACE: self._replace,
            CleaningActionType.FIND_REPLACE: self._find_and_replace,
            CleaningActionType.COPY_REPLACE: self._copy_and_replace,
            CleaningActionType.STRIP: self._strip_whitespace,
            CleaningActionType.TITLE_CASE: self._title_case,
            CleaningActionType.UPPER_CASE: self._upper_case,
            CleaningActionType.LOWER_CASE: self._lower_case,
            CleaningActionType.MAKE_NULL: self._make_null,
        }
        action_fn = action_map[self.cleaned_data['action']]
        self.column_manager.make_history_snapshot()
        num_changes = action_fn()
        if num_changes == 0:
            self.column_manager.rollback_history()
        return num_changes

    def _skip_row(self, row):
        return not row["selected"] or (self.filtered_ids and row["id"] not in self.filtered_ids)

    def _replace_with_value(self, new_value):
        num_changes = 0
        all_rows = self.column_manager.get_all_rows()
        slug = self.cleaned_data['slug']
        edited_slug = EditableColumn.get_edited_slug(slug)
        for row in all_rows:
            if self._skip_row(row):
                continue
            row[edited_slug] = new_value
            num_changes += 1
        self.column_manager.update_all_rows(all_rows)
        return num_changes

    def _replace(self):
        return self._replace_with_value(self.cleaned_data['replace_all_string'])

    def _make_null(self):
        return self._replace_with_value(Ellipsis)

    def make_edits_to_rows(self, update_fn, skip_null_value=True, is_string_only=True):
        num_changes = 0
        slug = self.cleaned_data['slug']
        edited_slug = EditableColumn.get_edited_slug(slug)
        all_rows = self.column_manager.get_all_rows()
        for row in all_rows:
            if self._skip_row(row):
                continue
            value = row.get(edited_slug, row[slug])

            if skip_null_value and (value is None or value is Ellipsis):
                continue

            if is_string_only:
                value = str(value)

            new_value = update_fn(value)

            if value != new_value:
                num_changes += 1

            if row[slug] != new_value:
                row[edited_slug] = new_value
            elif row.get(edited_slug):
                del row[edited_slug]

        self.column_manager.update_all_rows(all_rows)
        return num_changes

    def _find_and_replace(self):
        find_string = self.cleaned_data['find_string']
        replace_string = self.cleaned_data['replace_string']
        use_regex = self.cleaned_data['use_regex']

        def _find_replace_row_value(value):
            new_value = value
            if find_string and use_regex:
                new_value = re.sub(
                    re.compile(find_string),
                    replace_string,
                    value
                )
            elif find_string and find_string in value:
                new_value = value.replace(find_string, replace_string)
            elif find_string == value:
                new_value = replace_string
            return new_value

        return self.make_edits_to_rows(
            _find_replace_row_value
        )

    def _strip_whitespace(self):
        pattern = r"(^[\s]+)|([\s]+$)"

        def _strip_whitespaces_from_row_value(value):
            new_value = value
            if re.search(pattern, value):
                new_value = re.sub(pattern, '', value)
            return new_value

        return self.make_edits_to_rows(
            _strip_whitespaces_from_row_value
        )

    def _copy_and_replace(self):
        num_changes = 0
        all_rows = self.column_manager.get_all_rows()
        slug = self.cleaned_data['slug']
        edited_slug = EditableColumn.get_edited_slug(slug)
        copy_slug = self.cleaned_data['copy_slug']
        edited_copy_slug = EditableColumn.get_edited_slug(copy_slug)
        for row in all_rows:
            if self._skip_row(row):
                continue
            copied_value = row.get(edited_copy_slug, row[copy_slug])
            row[edited_slug] = copied_value
            num_changes += 1
        self.column_manager.update_all_rows(all_rows)
        return num_changes

    def _fix_words(self, fix_function):
        num_changes = 0
        words_pattern = r"([\S]+)"
        all_rows = self.column_manager.get_all_rows()
        slug = self.cleaned_data['slug']
        edited_slug = EditableColumn.get_edited_slug(slug)
        for row in all_rows:
            if self._skip_row(row):
                continue
            value = row.get(edited_slug, row[slug])
            if value is None:
                continue

            value = str(value)
            new_value = re.sub(
                words_pattern,
                fix_function,
                value
            )

            if value != new_value:
                num_changes += 1
            if row[slug] != new_value:
                row[edited_slug] = new_value
            elif row.get(edited_slug):
                del row[edited_slug]

        self.column_manager.update_all_rows(all_rows)
        return num_changes

    def _title_case(self):
        return self._fix_words(lambda x: x.group().capitalize())

    def _upper_case(self):
        return self._fix_words(lambda x: x.group().upper())

    def _lower_case(self):
        return self._fix_words(lambda x: x.group().lower())
