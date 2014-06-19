from django import forms
from django.forms import fields
from django.core.validators import validate_email
from .widgets import AutocompleteTextarea


class CSVListField(fields.CharField):
    """
        When you want a CharField that returns a list.
    """

    def to_python(self, value):
        if isinstance(value, list):
            return ", ".join(value)
        return [v.strip() for v in value.split(',')]

    def prepare_value(self, value):
        if isinstance(value, list):
            return ", ".join(value)
        return value


class MultiCharField(forms.Field):
    """
    A text field that expects a comma-separated list of inputs, and by default
    uses the AutocompleteTextarea widget, which uses a jQuery plugin to provide
    autocompletion (depends on Bootstrap) based on the 'choices' constructor
    argument.

    """
    widget = AutocompleteTextarea

    def __init__(self, initial=None, choices=(), *args, **kwargs):
        """
        choices - a list of choices to use as a source for autocompletion

        """
        if initial:
            initial = ', '.join(initial)
        super(MultiCharField, self).__init__(initial=initial, *args, **kwargs)

        self.choices = choices

    def _get_choices(self):
        return self._choices

    def _set_choices(self, value):
        self._choices = self.widget.choices = value
    
    choices = property(_get_choices, _set_choices)

    def to_python(self, value):
        if not value:
            return []

        return [val.strip() for val in value.split(',') if val.strip()]

    def run_validators(self, value):
        for val in value:
            if val not in self.choices:
                super(MultiCharField, self).run_validators(val)


class MultiEmailField(MultiCharField):
    """
    Validates that all provided emails are valid email addresses (or included
    in the 'choices' constructor argument).

    """
    default_validators = [validate_email]
    default_error_messages = {
        'invalid': 'Please enter only valid email addresses.'
    }
