import re

from django.core.exceptions import ValidationError


def validate_dhis2_uid(value):
    """
    Validates a `DHIS2 UID`_

        The DHIS2 UID format has these requirements:

        * 11 characters long.
        * Alphanumeric characters only, ie. alphabetic or numeric characters
          (A-Za-z0-9).
        * Start with an alphabetic character (A-Za-z).

    .. _DHIS2 UID: https://docs.dhis2.org/master/en/developer/html/webapi_system_resource.html
    """
    if not re.match('^[A-Za-z][A-Za-z0-9]{10}$', value):
        raise ValidationError(f'{value!r} is not a DHIS2 UID')
