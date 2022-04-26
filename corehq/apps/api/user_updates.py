from dimagi.utils.couch.bulk import get_docs

from corehq.apps.api.exceptions import (
    InvalidFormatException,
    UnknownFieldException,
    UpdateConflictException,
)
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.sms.util import strip_plus
from corehq.apps.user_importer.helpers import find_differences_in_list
from corehq.apps.users.audit.change_messages import UserChangeMessage


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
    }.get(field)

    if not update_fn:
        raise UnknownFieldException

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
        clean_password(password)
    user.set_password(password)

    if user_change_logger:
        user_change_logger.add_change_message(UserChangeMessage.password_reset())


def _update_default_phone_number(user, phone_number, user_change_logger):
    old_phone_numbers = set(user.phone_numbers)
    new_phone_numbers = set(user.phone_numbers)
    if not isinstance(phone_number, str):
        raise InvalidFormatException('string')
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


def _update_user_data(user, user_data, user_change_logger):
    original_user_data = user.metadata.copy()
    try:
        user.update_metadata(user_data)
    except ValueError as e:
        raise UpdateConflictException(str(e))

    if user_change_logger and original_user_data != user.user_data:
        user_change_logger.add_changes({'user_data': user.user_data})


def _simple_update(user, key, value, user_change_logger):
    if user_change_logger and getattr(user, key) != value:
        user_change_logger.add_changes({key: value})
    setattr(user, key, value)


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
