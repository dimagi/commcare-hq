from abc import ABCMeta, abstractmethod
from collections import Counter

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import ugettext as _

from dimagi.utils.parsing import string_to_boolean

from corehq.apps.domain.forms import clean_password
from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.users.forms import get_mobile_worker_max_username_length
from corehq.apps.users.util import normalize_username, raw_username


def get_user_import_validators(domain_obj, all_specs, allowed_groups=None, allowed_roles=None):
    domain = domain_obj.name
    validate_passwords = domain_obj.strong_mobile_passwords
    return [
        UsernameValidator(domain),
        IsActive(domain),
        UsernameOrUserIdRequired(domain),
        Duplicates(domain, 'username', all_specs),
        Duplicates(domain, 'user_id', all_specs),
        Duplicates(domain, 'password', all_specs, is_password) if validate_passwords else NoopValidator(domain),
        LongUsernames(domain),
        NewUserPassword(domain),
        PasswordValidator(domain) if validate_passwords else NoopValidator(domain),
        CustomDataValidator(domain),
        EmailValidator(domain),
        GroupValidator(domain, allowed_groups),
        RoleValidator(domain, allowed_roles),
    ]


class ImportValidator(metaclass=ABCMeta):
    error_message = None

    def __init__(self, domain):
        self.domain = domain

    def __call__(self, spec):
        error = self.validate_spec(spec)
        if error:
            raise UserUploadError(error)

    @abstractmethod
    def validate_spec(self, spec):
        raise NotImplementedError


class NoopValidator(ImportValidator):
    def validate_spec(self, spec):
        pass


class UsernameValidator(ImportValidator):
    error_message = _('username cannot contain spaces or symbols')

    def validate_spec(self, spec):
        username = spec.get('username')
        try:
            normalize_username(str(username), self.domain)
        except TypeError:
            pass
        except ValidationError:
            return self.error_message


class IsActive(ImportValidator):
    error_message = _("'is_active' column can only contain 'true' or 'false'")

    def validate_spec(self, spec):
        is_active = spec.get('is_active')
        if isinstance(is_active, str):
            try:
                string_to_boolean(is_active) if is_active else None
            except ValueError:
                return self.error_message


class UsernameOrUserIdRequired(ImportValidator):
    error_message = _("One of 'username' or 'user_id' is required")

    def validate_spec(self, spec):
        user_id = spec.get('user_id')
        username = spec.get('username')
        if not user_id and not username:
            return self.error_message


class Duplicates(ImportValidator):
    _error_message = _("'{field}' values must be unique")

    def __init__(self, domain, field, all_specs, check_function=None):
        super().__init__(domain)
        self.field = field
        self.check_function = check_function
        self.duplicates = find_duplicates(all_specs, field)

    @property
    def error_message(self):
        return self._error_message.format(field=self.field)

    def validate_spec(self, row_spec):
        item = row_spec.get(self.field)
        if not item:
            return

        if self.check_function and not self.check_function(item):
            return

        if item in self.duplicates:
            return self.error_message


def find_duplicates(specs, field):
    counter = Counter([
        spec.get(field) for spec in specs
    ])
    return {
        value for value, count in counter.items() if count > 1
    }


class LongUsernames(ImportValidator):
    _error_message = _("username cannot contain greater than {length} characters")

    def __init__(self, domain, max_length=None):
        super().__init__(domain)
        self.max_username_length = max_length or get_mobile_worker_max_username_length(self.domain)

    @property
    def error_message(self):
        return self._error_message.format(length=self.max_username_length)

    def validate_spec(self, spec):
        username = spec.get('username')
        if len(raw_username(username)) > self.max_username_length:
            return self.error_message


class NewUserPassword(ImportValidator):
    error_message = _("New users must have a password set.")

    def validate_spec(self, spec):
        user_id = spec.get('user_id')
        password = spec.get('password')
        if not user_id and not is_password(password):
            return self.error_message


class PasswordValidator(ImportValidator):
    def validate_spec(self, spec):
        password = spec.get('password')
        if is_password(password):
            try:
                clean_password(password)
            except ValidationError as e:
                return e.message


class CustomDataValidator(ImportValidator):
    def __init__(self, domain):
        super().__init__(domain)
        from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
        self.custom_data_validator = UserFieldsView.get_validator(domain)

    def validate_spec(self, spec):
        data = spec.get('data')
        if data:
            return self.custom_data_validator(data)


class EmailValidator(ImportValidator):
    error_message = _("User has an invalid email address")

    def validate_spec(self, spec):
        email = spec.get('email')
        if email:
            try:
                validate_email(email)
            except ValidationError:
                return self.error_message


class RoleValidator(ImportValidator):
    error_message = _("Role '{}' does not exist")

    def __init__(self, domain, allowed_roles=None):
        super().__init__(domain)
        self.allowed_roles = allowed_roles

    def validate_spec(self, spec):
        role = spec.get('role')
        if role and role not in self.allowed_roles:
            return self.error_message.format(role)


class GroupValidator(ImportValidator):
    error_message = _("Group '{}' does not exist (try adding it to your spreadsheet)")

    def __init__(self, domain, allowed_groups=None):
        super().__init__(domain)
        self.allowed_groups = allowed_groups

    def validate_spec(self, spec):
        group_names = list(map(str, spec.get('group') or []))
        for group_name in group_names:
            if group_name not in self.allowed_groups:
                return self.error_message.format(group_name)


def is_password(password):
    if not password:
        return False
    for c in str(password):
        if c != "*":
            return True
    return False
