from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from corehq.apps.users.dbaccessors import user_exists
from corehq.apps.users.exceptions import (
    InvalidUsernameException,
    ReservedUsernameException,
    UsernameAlreadyExists,
)
from corehq.apps.users.util import format_username
from corehq.apps.users.views.mobile import BAD_MOBILE_USERNAME_REGEX


def validate_mobile_username(username, domain):
    _check_for_reserved_usernames(username)
    username_as_email = format_username(username, domain)
    _ensure_valid_username(username_as_email)
    _ensure_username_is_available(username_as_email)
    return username_as_email


def _check_for_reserved_usernames(username):
    reserved_usernames = ['admin', 'demo_user']
    if username in reserved_usernames:
        raise ReservedUsernameException


def _ensure_valid_username(username):
    try:
        validate_email(username)
    except ValidationError:
        raise InvalidUsernameException

    if BAD_MOBILE_USERNAME_REGEX.search(username) is not None:
        raise InvalidUsernameException


def _ensure_username_is_available(username):
    exists = user_exists(username)
    if exists.exists:
        raise UsernameAlreadyExists(is_deleted=exists.is_deleted)
