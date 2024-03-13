from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from dimagi.utils.couch.bulk import get_docs

from corehq.apps.api.exceptions import UpdateUserException
from corehq.apps.custom_data_fields.models import PROFILE_SLUG
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.sms.util import strip_plus
from corehq.apps.user_importer.helpers import find_differences_in_list
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.user_data import UserDataError


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

    if user_change_logger and changed:
        user_change_logger.add_changes({
            'user_data': user.get_user_data(user.domain).raw
        })


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
