from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext as _

from corehq.apps.users.util import is_username_available
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.util import get_locations_from_ids
from corehq.apps.users.views.mobile import BAD_MOBILE_USERNAME_REGEX
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView


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


def validate_profile_required(profile_name, domain):
    profile_required_for_user_type_list = CustomDataFieldsDefinition.get_profile_required_for_user_type_list(
        domain,
        UserFieldsView.field_type
    )
    if not profile_required_for_user_type_list:
        return
    profile_assginment_required = UserFieldsView.COMMCARE_USER in profile_required_for_user_type_list
    if profile_assginment_required and not profile_name:
        raise ValidationError(
            _("A profile assignment is required for Mobile Workers.")
        )


def validate_assigned_locations_allow_users(domain, assigned_location_ids):
    error_message_location_not_has_users = _("These locations cannot have users assigned because of their "
                                             "organization level settings: {}.")
    try:
        locs_being_assigned = get_locations_from_ids(assigned_location_ids, domain)
    except SQLLocation.DoesNotExist:
        return _('One or more of the locations was not found.')
    problem_locations = locs_being_assigned.filter(location_type__has_users=False)
    if problem_locations:
        return error_message_location_not_has_users.format(
            ', '.join(problem_locations.values_list('site_code', flat=True)))


def validate_primary_location_assignment(primary_location, assigned_locations):
    if primary_location:
        if primary_location not in assigned_locations:
            return _("Primary location must be one of the user's locations")
    if assigned_locations and not primary_location:
        return _("Primary location can't be empty if the user has any locations set")
