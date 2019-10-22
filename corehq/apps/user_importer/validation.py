from abc import ABCMeta, abstractmethod

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.users.util import normalize_username
from dimagi.utils.parsing import string_to_boolean


def get_user_import_validators(domain):
    return [
        UsernameValidator(domain),
        IsActive(domain),
        UsernameOrUserIdRequired(domain),
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
