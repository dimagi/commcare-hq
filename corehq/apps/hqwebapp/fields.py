from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.forms import fields
from django.utils.translation import gettext_lazy as _

import requests

from dimagi.utils.web import get_ip

from corehq.apps.hqwebapp.widgets import TurnstileWidget
from corehq.util.global_request import get_request

TURNSTILE_SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
TURNSTILE_VERIFY_TIMEOUT_SECONDS = 5


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


class TurnstileField(forms.Field):
    """A Cloudflare Turnstile bot check, for forms served to the public.

    TURNSTILE_SECRET_KEY and TURNSTILE_SITE_KEY must be defined in settings, and
    ``https://challenges.cloudflare.com/turnstile/v0/api.js`` loaded on the page.
    """

    widget = TurnstileWidget
    default_error_messages = {
        'required': _("Please confirm that you are not a robot."),
        'invalid': _("We could not confirm that you are not a robot. Please try again."),
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('label', '')
        super().__init__(**kwargs)
        self.required = True

    def validate(self, value):
        if not settings.TURNSTILE_SECRET_KEY:
            return
        super().validate(value)
        if not self._is_token_valid(value):
            raise ValidationError(self.error_messages['invalid'])

    def _is_token_valid(self, token):
        request = get_request()
        try:
            response = requests.post(
                TURNSTILE_SITEVERIFY_URL,
                data={
                    'secret': settings.TURNSTILE_SECRET_KEY,
                    'response': token,
                    'remoteip': get_ip(request) if request else None,
                },
                timeout=TURNSTILE_VERIFY_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException:
            return False
        return bool(result.get('success'))
