from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from phonenumber_field.phonenumber import to_python

# This is based on the two_factor international phonenumber validator. This is the only place we explicitly depend
# on django-phonenumber-field, but we need to define our own validator because the HQPhoneNumberForm that relies on
# this validator sets the phonenumber field to not required, which allows the user to navigate back in the setup
# process without filling out a valid phonenumber. The back button on that form is of type 'submit' which seems
# necessary to properly update the underlying 2FA wizard setup provided by django-two-factor-auth.


def validate_international_phonenumber(value):
    phone_number = to_python(value)
    if not phone_number or not phone_number.is_valid():
        raise ValidationError(validate_international_phonenumber.message,
                              code='invalid')


validate_international_phonenumber.message = \
    _('Make sure to enter a valid phone number '
      'starting with a +, followed by your country code.')
validators = [validate_international_phonenumber]
