from django import forms
from django.core.validators import validate_email
from django.forms import fields


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
    uses select2 widget that allows for multiple selections and accepts free text.
    """
    widget = forms.SelectMultiple(attrs={'class': 'hqwebapp-autocomplete-email form-control'})

    def __init__(self, initial=None, choices=(), *args, **kwargs):
        """
        choices - a list of choices to use as a source for autocompletion
        """
        super(MultiCharField, self).__init__(initial=initial, *args, **kwargs)

        self.choices = choices

    def _get_choices(self):
        return self._choices

    def _set_choices(self, value):
        self._choices = value
        self.widget.choices = value

    choices = property(_get_choices, _set_choices)

    def run_validators(self, value):
        if value in self.empty_values:
            return

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
