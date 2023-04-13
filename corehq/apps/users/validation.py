from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext as _

from corehq.apps.users.util import is_username_available
from corehq.apps.users.views.mobile import BAD_MOBILE_USERNAME_REGEX


def validate_mobile_username(username, domain, is_unique=True):
    """
    Raises a ValidationError if any issue with the complete username is encountered
    :param username: str, expects complete username ('username@example.commcarehq.org')
    :param domain: str, required
    :param is_unique: if true then username should not already exist.
    """
    if not username:
        raise ValidationError(_("Username is required."))

    _validate_complete_username(username, domain)

    if is_unique and not is_username_available(username):
        raise ValidationError(_("Username '{}' is already taken or reserved.").format(username))


def _validate_complete_username(username, domain):
    """
    Raises a ValidationError if the username is invalid
    :param username: expects str formatted like 'username@example.commcarehq.org'
    """
    try:
        validate_email(username)
    except ValidationError:
        raise ValidationError(_("Username '{}' must be a valid email address.").format(username))

    email_username, email_domain = username.split('@')
    if BAD_MOBILE_USERNAME_REGEX.search(email_username) is not None:
        raise ValidationError(
            _("The username component '{}' of '{}' may not contain special characters.").format(
                email_username, username)
        )

    expected_domain = f"{domain}.commcarehq.org"
    if email_domain != expected_domain:
        raise ValidationError(
            _("The username email domain '@{}' should be '@{}'.").format(email_domain, expected_domain))
