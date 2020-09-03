from abc import ABCMeta, abstractmethod
from collections import Counter

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import ugettext as _

from corehq.apps.user_importer.helpers import spec_value_to_boolean_or_none
from corehq.apps.users.dbaccessors.all_commcare_users import get_existing_usernames
from dimagi.utils.chunked import chunked
from dimagi.utils.parsing import string_to_boolean

from corehq.apps.domain.forms import clean_password
from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.users.forms import get_mobile_worker_max_username_length
from corehq.apps.users.models import DomainPermissionsMirror
from corehq.apps.users.util import normalize_username, raw_username
from corehq.util.workbook_json.excel import (
    StringTypeRequiredError,
    enforce_string_type,
)


def get_user_import_validators(domain_obj, all_specs, allowed_groups=None, allowed_roles=None, upload_domain=None):
    domain = domain_obj.name
    validate_passwords = domain_obj.strong_mobile_passwords
    noop = NoopValidator(domain)
    return [
        UsernameTypeValidator(domain),
        UsernameValidator(domain),
        BooleanColumnValidator(domain, 'is_active'),
        BooleanColumnValidator(domain, 'is_account_confirmed'),
        BooleanColumnValidator(domain, 'send_confirmation_email'),
        RequiredFieldsValidator(domain),
        DuplicateValidator(domain, 'username', all_specs),
        DuplicateValidator(domain, 'user_id', all_specs),
        DuplicateValidator(domain, 'password', all_specs, is_password) if validate_passwords else noop,
        UsernameLengthValidator(domain),
        NewUserPasswordValidator(domain),
        PasswordValidator(domain) if validate_passwords else noop,
        CustomDataValidator(domain),
        EmailValidator(domain),
        GroupValidator(domain, allowed_groups),
        RoleValidator(domain, allowed_roles),
        ExistingUserValidator(domain, all_specs),
        TargetDomainValidator(upload_domain)
    ]


class ImportValidator(metaclass=ABCMeta):
    error_message = None

    def __init__(self, domain):
        self.domain = domain

    def __call__(self, spec):
        error_message = self.validate_spec(spec)
        if error_message:
            raise UserUploadError(error_message)

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
        if username:
            try:
                normalize_username(str(username), self.domain)
            except TypeError:
                pass
            except ValidationError:
                return self.error_message


class BooleanColumnValidator(ImportValidator):
    _error_message = _("'{column_id}' column can only contain 'true' or 'false'")

    def __init__(self, domain, column_id):
        self.column_id = column_id
        super().__init__(domain)

    def validate_spec(self, spec):
        value = spec.get(self.column_id)
        if isinstance(value, str):
            try:
                string_to_boolean(value) if value else None
            except ValueError:
                return self.error_message

    @property
    def error_message(self):
        return self._error_message.format(column_id=self.column_id)


class RequiredFieldsValidator(ImportValidator):
    error_message = _("One of 'username' or 'user_id' is required")

    def validate_spec(self, spec):
        user_id = spec.get('user_id')
        username = spec.get('username')
        if not user_id and not username:
            return self.error_message


class DuplicateValidator(ImportValidator):
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


class UsernameLengthValidator(ImportValidator):
    _error_message = _("username cannot contain greater than {length} characters")

    def __init__(self, domain, max_length=None):
        super().__init__(domain)
        self.max_username_length = max_length or get_mobile_worker_max_username_length(self.domain)

    @property
    def error_message(self):
        return self._error_message.format(length=self.max_username_length)

    def validate_spec(self, spec):
        username = spec.get('username')
        if username:
            username = str(username)
        if len(raw_username(username)) > self.max_username_length:
            return self.error_message


class UsernameTypeValidator(ImportValidator):
    error_message = _("Username must be Text")

    def validate_spec(self, spec):
        username = spec.get('username')
        if not username:
            return
        try:
            enforce_string_type(username)
        except StringTypeRequiredError:
            return self.error_message


class NewUserPasswordValidator(ImportValidator):
    error_message = _("New users must have a password set.")

    def validate_spec(self, spec):
        user_id = spec.get('user_id')
        password = spec.get('password')
        is_account_confirmed = spec_value_to_boolean_or_none(spec, 'is_account_confirmed')
        web_user = spec.get('web_user')

        # explicitly check is_account_confirmed against False because None is the default
        if not user_id and not is_password(password) and is_account_confirmed is not False and not web_user:
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


class ExistingUserValidator(ImportValidator):
    error_message = _("The username already belongs to a user. Specify an ID to update the user.")

    def __init__(self, domain, all_sepcs):
        super().__init__(domain)
        self.all_specs = all_sepcs
        self.existing_usernames = self.get_exising_users()

    def get_exising_users(self):
        usernames_without_ids = set()

        for row in self.all_specs:
            username = row.get('username')
            if row.get('user_id') or not username:
                continue

            try:
                usernames_without_ids.add(normalize_username(username, self.domain))
            except ValidationError:
                pass

        existing_usernames = set()
        for usernames in chunked(usernames_without_ids, 500):
            existing_usernames.update(get_existing_usernames(usernames))

        return existing_usernames

    def validate_spec(self, spec):
        try:
            username = normalize_username(spec.get('username'), self.domain)
        except ValidationError:
            return

        if username in self.existing_usernames:
            return self.error_message


class TargetDomainValidator(ImportValidator):
    error_message = _("Target domain {} is not a mirror of {}")

    def validate_spec(self, spec):
        target_domain = spec.get('domain')
        if target_domain and target_domain != self.domain:
            mirror_domains = DomainPermissionsMirror.mirror_domains(self.domain)
            if target_domain not in mirror_domains:
                return self.error_message.format(target_domain, self.domain)
