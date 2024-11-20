from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from corehq.apps.locations.models import SQLLocation

from dimagi.utils.couch.bulk import get_docs

from corehq.apps.api.exceptions import UpdateUserException
from corehq.apps.custom_data_fields.models import PROFILE_SLUG, CustomDataFieldsProfile
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.sms.util import strip_plus
from corehq.apps.user_importer.helpers import find_differences_in_list
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.user_data import UserDataError
from corehq.apps.users.validation import validate_profile_required


def update(user, field, value, user_change_logger=None):
    """
    Used to update user fields via the API
    Raises exceptions if errors are encountered, otherwise the update is successful
    :param user: CommCareUser object
    :param field: the attribute on the user to update
    :param value: the value to update the attribute to
    :param user_change_logger: optional UserChangeLogger obj to log changes
    """
    update_fn = {
        'default_phone_number': _update_default_phone_number,
        'email': _update_email,
        'first_name': _update_first_name,
        'groups': _update_groups,
        'language': _update_language,
        'last_name': _update_last_name,
        'password': _update_password,
        'phone_numbers': _update_phone_numbers,
        'user_data': _update_user_data,
        'role': _update_user_role,
        'location': _update_location,
    }.get(field)

    if not update_fn:
        raise UpdateUserException(_("Attempted to update unknown or non-editable field '{}'").format(field))

    update_fn(user, value, user_change_logger)


def _update_email(user, email, user_change_logger):
    _simple_update(user, 'email', email.lower(), user_change_logger)


def _update_first_name(user, first_name, user_change_logger):
    _simple_update(user, 'first_name', first_name, user_change_logger)


def _update_last_name(user, last_name, user_change_logger):
    _simple_update(user, 'last_name', last_name, user_change_logger)


def _update_language(user, language, user_change_logger):
    _simple_update(user, 'language', language, user_change_logger)


def _update_password(user, password, user_change_logger):
    domain = Domain.get_by_name(user.domain)
    if domain.strong_mobile_passwords:
        try:
            clean_password(password)
        except ValidationError:
            raise UpdateUserException(_("Password is not strong enough."))
    user.set_password(password)

    if user_change_logger:
        user_change_logger.add_change_message(UserChangeMessage.password_reset())


def _update_default_phone_number(user, phone_number, user_change_logger):
    old_phone_numbers = set(user.phone_numbers)
    new_phone_numbers = set(user.phone_numbers)
    if not isinstance(phone_number, str):
        raise UpdateUserException(_("'default_phone_number' must be a string"))
    formatted_phone_number = strip_plus(phone_number)
    new_phone_numbers.add(formatted_phone_number)
    user.set_default_phone_number(formatted_phone_number)

    if user_change_logger:
        _log_phone_number_change(new_phone_numbers, old_phone_numbers, user_change_logger)


def _update_phone_numbers(user, phone_numbers, user_change_logger):
    old_phone_numbers = set(user.phone_numbers)
    new_phone_numbers = set()
    user.phone_numbers = []
    for idx, phone_number in enumerate(phone_numbers):
        formatted_phone_number = strip_plus(phone_number)
        new_phone_numbers.add(formatted_phone_number)
        user.add_phone_number(formatted_phone_number)
        if idx == 0:
            user.set_default_phone_number(formatted_phone_number)

    if user_change_logger:
        _log_phone_number_change(new_phone_numbers, old_phone_numbers, user_change_logger)


def _update_groups(user, group_ids, user_change_logger):
    groups_updated = user.set_groups(group_ids)
    if user_change_logger and groups_updated:
        groups = []
        if group_ids:
            groups = [Group.wrap(doc) for doc in get_docs(Group.get_db(), group_ids)]
        user_change_logger.add_info(UserChangeMessage.groups_info(groups))


def _update_user_data(user, new_user_data, user_change_logger):
    try:
        profile_id = new_user_data.pop(PROFILE_SLUG, ...)
        changed = user.get_user_data(user.domain).update(new_user_data, profile_id=profile_id)
    except UserDataError as e:
        raise UpdateUserException(str(e))
    try:
        if profile_id != ...:
            profile = CustomDataFieldsProfile.objects.get(id=profile_id)
            if profile:
                profile_name = profile.name
        else:
            profile_name = None
        validate_profile_required(profile_name, user.domain)
    except ValidationError as e:
        raise UpdateUserException(_(e.message))
    if user_change_logger and changed:
        user_change_logger.add_changes({
            'user_data': user.get_user_data(user.domain).raw
        }, skip_confirmation=True)


def _update_user_role(user, role, user_change_logger):
    roles = UserRole.objects.by_domain_and_name(user.domain, role)
    if not roles:
        raise UpdateUserException(_("The role '{}' does not exist").format(role))
    if len(roles) > 1:
        raise UpdateUserException(
            _("There are multiple roles with the name '{}' in the domain '{}'").format(role, user.domain)
        )

    original_role = user.get_role(user.domain)
    new_role = roles[0]
    if not original_role or original_role.get_qualified_id() != new_role.get_qualified_id():
        user.set_role(user.domain, new_role.get_qualified_id())
        if user_change_logger:
            user_change_logger.add_info(UserChangeMessage.role_change(new_role))


def _simple_update(user, key, value, user_change_logger):
    if getattr(user, key) != value:
        setattr(user, key, value)
        if user_change_logger:
            user_change_logger.add_changes({key: value})


def _log_phone_number_change(new_phone_numbers, old_phone_numbers, user_change_logger):
    numbers_added, numbers_removed = find_differences_in_list(
        target=list(new_phone_numbers),
        source=list(old_phone_numbers)
    )

    change_messages = {}
    if numbers_removed:
        change_messages.update(
            UserChangeMessage.phone_numbers_removed(list(numbers_removed))["phone_numbers"]
        )

    if numbers_added:
        change_messages.update(
            UserChangeMessage.phone_numbers_added(list(numbers_added))["phone_numbers"]
        )

    if change_messages:
        user_change_logger.add_change_message({'phone_numbers': change_messages})


def _update_location(user, location_object, user_change_logger):
    primary_location_id = location_object.get('primary_location')
    location_ids = location_object.get('locations')

    if primary_location_id is None and location_ids is None:
        return

    current_primary_location_id = user.get_location_id(user.domain)
    current_locations = user.get_location_ids(user.domain)

    if not primary_location_id and not location_ids:
        _remove_all_locations(user, user_change_logger)
    else:
        if _validate_locations(primary_location_id, location_ids):
            locations = _verify_location_ids(location_ids, user.domain)
            if primary_location_id != current_primary_location_id:
                _update_primary_location(user, primary_location_id, user_change_logger)
            if set(current_locations) != set(location_ids):
                _update_assigned_locations(user, locations, location_ids, user_change_logger)


def _validate_locations(primary_location_id, location_ids):
    if not primary_location_id and not location_ids:
        return False
    if not primary_location_id or not location_ids:
        raise UpdateUserException(_('Both primary_location and locations must be provided together.'))
    if primary_location_id not in location_ids:
        raise UpdateUserException(_('Primary location must be included in the list of locations.'))
    return True


def _remove_all_locations(user, user_change_logger):
    user.unset_location(commit=False)
    user.reset_locations([], commit=False)
    if user_change_logger:
        user_change_logger.add_changes({'location_id': None})
        user_change_logger.add_info(UserChangeMessage.primary_location_removed())
        user_change_logger.add_changes({'assigned_location_ids': []})
        user_change_logger.add_info(UserChangeMessage.assigned_locations_info([]))


def _update_primary_location(user, primary_location_id, user_change_logger):
    primary_location = SQLLocation.active_objects.get(location_id=primary_location_id)
    user.set_location(primary_location, commit=False)
    if user_change_logger:
        user_change_logger.add_changes({'location_id': primary_location_id})
        user_change_logger.add_info(UserChangeMessage.primary_location_info(primary_location))


def _verify_location_ids(location_ids, domain):
    locations = SQLLocation.active_objects.filter(location_id__in=location_ids, domain=domain)
    real_ids = [loc.location_id for loc in locations]

    if missing_ids := set(location_ids) - set(real_ids):
        raise UpdateUserException(f"Could not find location ids: {', '.join(missing_ids)}.")

    return locations


def _update_assigned_locations(user, locations, location_ids, user_change_logger):
    user.reset_locations(location_ids, commit=False)
    if user_change_logger:
        user_change_logger.add_changes({'assigned_location_ids': location_ids})
        user_change_logger.add_info(UserChangeMessage.assigned_locations_info(locations))
