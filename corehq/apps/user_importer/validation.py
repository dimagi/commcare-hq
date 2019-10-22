from abc import ABCMeta, abstractmethod

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.users.util import normalize_username


def get_user_import_validators(domain):
    return [
        UsernameValidator(domain)
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
