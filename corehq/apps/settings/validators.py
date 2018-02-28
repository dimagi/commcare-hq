from __future__ import absolute_import
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from phonenumber_field.phonenumber import to_python


def validate_international_phonenumber(value):
    phone_number = to_python(value)
    if not phone_number or not phone_number.is_valid():
        raise ValidationError(validate_international_phonenumber.message,
                              code='invalid')


validate_international_phonenumber.message = \
    _('Make sure to enter a valid phone number '
      'starting with a +, followed by your country code.')


def run_validators(self, value):
    # Validator that doesn't ignore none's
    errors = []
    for v in self.validators:
        try:
            v(value)
        except ValidationError as e:
            if hasattr(e, 'code') and e.code in self.error_messages:
                e.message = self.error_messages[e.code]
            errors.extend(e.error_list)
    if errors:
        raise ValidationError(errors)
