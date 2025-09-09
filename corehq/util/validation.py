import re

from corehq.util.urlvalidate.urlvalidate import validate_user_input_url, InvalidURL, PossibleSSRFAttempt
import jsonschema
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

BANNED_HOST_REGEX = (
    r'commcarehq\.org',
    r'10\..*\..*\..*',
    r'172.1[6-9]\..*\..*',
    r'172.2[0-9]\..*\..*',
    r'172.3[0-1]\..*\..*',
    r'192.168\..*\..*',
    r'127.0.0.1',
    r'localhost',
)


def is_url_or_host_banned(url_or_host):
    # We should never be accepting user-entered urls that we then connect to, and
    # all urls should always be configured only by site admins. However, we can
    # use this check to help site admins ensure they're not making any obvious
    # mistakes.
    black_list_result = any([re.search(regex, url_or_host) for regex in BANNED_HOST_REGEX])
    if black_list_result:
        return True

    url = url_or_host if has_scheme(url_or_host) else f'http://{url_or_host}'
    try:
        validate_user_input_url(url)
        return False
    except (InvalidURL, PossibleSSRFAttempt):
        return True


def has_scheme(url):
    scheme_regex = r'^(?:[^:]+:)?//'  # Should match 'http://', 'file://', '//' etc
    return bool(re.match(scheme_regex, url))


@deconstructible
class JSONSchemaValidator:
    """Field level validation for JSONField against a JSON Schema"""

    def __init__(self, schema):
        self.schema = schema
        self.schema_validator_class = jsonschema.validators.validator_for(schema)
        self.schema_validator_class.check_schema(schema)

    def __call__(self, value):
        errors = self.schema_validator_class(self.schema).iter_errors(value)

        def _extract_errors(_errors):
            for error in _errors:
                if error.context:
                    return _extract_errors(error.context)

                message = str(error).replace("\n\n", ": ").replace("\n", "")
                django_errors.append(ValidationError(message))

        django_errors = []
        _extract_errors(errors)
        if django_errors:
            raise ValidationError(django_errors)

        return value

    def __eq__(self, other):
        if not hasattr(other, 'deconstruct'):
            return False
        return self.deconstruct() == other.deconstruct()
