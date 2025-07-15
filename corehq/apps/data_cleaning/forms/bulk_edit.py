import json
import re

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.data_cleaning.models import (
    BulkEditChange,
    EditActionType,
)
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import AlpineSelect, BootstrapSwitchInput


class EditSelectedRecordsForm(forms.Form):
    """
    NOTE: While the related forms for this feature share similar properties (`prop_id`)
    the `edit_` prefix is used here because all forms will be inserted into the same DOM, resulting
    in the same css ids for each field (generated as `id_<field slug>`). Having multiple elements
    with the same id is invalid HTML. Additionally, this scenario will result in select2s being
    applied to only ONE field.
    """

    edit_prop_id = forms.ChoiceField(
        label=gettext_lazy('Select a property to edit'),
        required=False,
        help_text=gettext_lazy(
            'You can only select editable case properties that are currently visible in '
            'the table as a column. System properties cannot be edited.'
        ),
    )
    edit_action = forms.ChoiceField(
        label=gettext_lazy('Edit action'),
        widget=AlpineSelect,
        choices=EditActionType.CHOICES,
        required=False,
    )
    find_string = forms.CharField(
        label=gettext_lazy('Find:'),
        strip=False,
        required=False,
    )
    use_regex = forms.CharField(
        label='',
        required=False,
        widget=BootstrapSwitchInput(
            inline_label=gettext_lazy('Use regular expression'),
        ),
    )
    replace_string = forms.CharField(
        label=gettext_lazy('Replace with:'),
        strip=False,
        required=False,
    )
    replace_all_string = forms.CharField(
        label=gettext_lazy('Replace existing value with:'),
        strip=False,
        required=False,
    )
    copy_from_prop_id = forms.ChoiceField(
        label=gettext_lazy('Copy from property:'),
        choices=(),
        required=False,
        help_text=gettext_lazy(
            'The value from this property will replace the value from the selected property at the top.'
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
        self.fields['edit_prop_id'].choices = property_choices
        self.fields['copy_from_prop_id'].choices = property_choices

        initial_prop_id = self.data.get('edit_prop_id')

        offcanvas_selector = '#offcanvas-bulk-changes'

        alpine_data_model = {
            'propId': initial_prop_id,
            'editAction': self.data.get('edit_action', EditActionType.CHOICES[0][0]),
            'replaceActions': [EditActionType.REPLACE],
            'findActions': [EditActionType.FIND_REPLACE],
            'copyActions': [EditActionType.COPY_REPLACE],
        }

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'edit_prop_id',
                    x_select2=json.dumps(
                        {
                            'placeholder': _('Select a case property...'),
                            'dropdownParent': offcanvas_selector,
                        }
                    ),
                    **(
                        {
                            '@select2change': 'propId = $event.detail;',
                        }
                    ),
                ),
                crispy.Div(
                    crispy.Field(
                        'edit_action',
                        x_select2=json.dumps(
                            {
                                'placeholder': _('Select an edit action...'),
                                'dropdownParent': offcanvas_selector,
                            }
                        ),
                        **(
                            {
                                '@select2change': 'editAction = $event.detail;',
                            }
                        ),
                    ),
                    crispy.Div(
                        crispy.Div(
                            'replace_all_string',
                            css_class='card-body',
                        ),
                        x_show='replaceActions.includes(editAction)',
                        css_class='card mb-3',
                    ),
                    crispy.Div(
                        crispy.Div(
                            'find_string',
                            hqcrispy.CheckboxField('use_regex'),
                            'replace_string',
                            css_class='card-body',
                        ),
                        x_show='findActions.includes(editAction)',
                        css_class='card mb-3',
                    ),
                    crispy.Div(
                        crispy.Div(
                            crispy.Field(
                                'copy_from_prop_id',
                                x_select2=json.dumps(
                                    {
                                        'placeholder': _('Select a case property...'),
                                        'dropdownParent': offcanvas_selector,
                                    }
                                ),
                            ),
                            css_class='card-body',
                        ),
                        x_show='copyActions.includes(editAction)',
                        css_class='card mb-3',
                    ),
                    twbscrispy.StrictButton(
                        _('Preview Edits'),
                        type='submit',
                        css_class='btn-primary',
                    ),
                    x_show='propId',
                ),
                x_data=json.dumps(alpine_data_model),
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        edit_action = cleaned_data.get('edit_action')

        if edit_action == EditActionType.REPLACE:
            if not cleaned_data.get('replace_all_string'):
                self.add_error(
                    'replace_all_string',
                    _('Please specify a value you would like to replace the existing property value with.'),
                )
                return cleaned_data

        if edit_action == EditActionType.FIND_REPLACE:
            # note: allow empty replace_string

            find_string = cleaned_data.get('find_string')
            if not find_string:
                self.add_error('find_string', _('Please specify the value you would like to find.'))
                return cleaned_data

            use_regex = cleaned_data.get('use_regex')
            if use_regex:
                try:
                    re.compile(find_string)
                except re.error:
                    self.add_error('find_string', _('Not a valid regular expression.'))
                    return cleaned_data

        if edit_action == EditActionType.COPY_REPLACE:
            copy_from_prop_id = cleaned_data.get('copy_from_prop_id')
            if not copy_from_prop_id:
                self.add_error(
                    'copy_from_prop_id',
                    _('Please select a property to copy from.'),
                )
                return cleaned_data
            if copy_from_prop_id == cleaned_data.get('edit_prop_id'):
                self.add_error(
                    'copy_from_prop_id',
                    _('You cannot copy from the same property.'),
                )
                return cleaned_data

        return cleaned_data

    def get_bulk_edit_change(self):
        prop_id = self.cleaned_data['edit_prop_id']
        action_type = self.cleaned_data['edit_action']
        if action_type == EditActionType.REPLACE:
            action_options = {
                'replace_string': self.cleaned_data['replace_all_string'],
            }
        elif action_type == EditActionType.FIND_REPLACE:
            action_options = {
                'find_string': self.cleaned_data['find_string'],
                'replace_string': self.cleaned_data['replace_string'],
                'use_regex': self.cleaned_data['use_regex'],
            }
        elif action_type == EditActionType.COPY_REPLACE:
            action_options = {
                'copy_from_prop_id': self.cleaned_data['copy_from_prop_id'],
            }
        else:
            action_options = {}
        return BulkEditChange(
            session=self.session,
            prop_id=prop_id,
            action_type=action_type,
            **action_options,
        )
