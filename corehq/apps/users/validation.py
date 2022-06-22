from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext as _

from corehq.apps.users.util import format_username, is_username_available
from corehq.apps.users.views.mobile import BAD_MOBILE_USERNAME_REGEX


def validate_mobile_username(username, domain):
    """
    Returns the email formatted mobile username if valid
    Otherwise raises custom exceptions based on the issue encountered with the username
    :param username: str, required
    :param domain: str, required
    :return: str, email formatted mobile username
    Example: validate_mobile_username('username', 'domain') -> 'username@domain.commcarehq.org'
    """
    if not username:
        raise ValidationError(_("Username is required."))

    username_as_email = format_username(username, domain)
    _validate_complete_username(username_as_email)

    if not is_username_available(username_as_email):
        raise ValidationError(_("Username '{}' is already taken or reserved.").format(username_as_email))

    return username_as_email


def _validate_complete_username(username):
    """
    Raises a ValidationError if the username is invalid
    :param username: expects str formatted like 'username@example.commcarehq.org'
    """
    try:
        validate_email(username)
    except ValidationError:
        raise ValidationError(_("Username '{}' must be a valid email address.").format(username))

    email_username = username.split('@')[0]
    if BAD_MOBILE_USERNAME_REGEX.search(email_username) is not None:
        raise ValidationError(
            _("The username component '{}' of '{}' may not contain special characters.").format(
                email_username, username)
        )
