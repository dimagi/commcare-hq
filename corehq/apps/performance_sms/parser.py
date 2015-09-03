from collections import namedtuple
from string import Formatter
from django.utils.translation import ugettext as _
import re
from corehq.apps.performance_sms.exceptions import InvalidParameterException

GLOBAL_NAMESPACE = 'global'
USER_NAMESPACE = 'user'
GROUP_NAMESPACE = 'group'
VALID_NAMESPACES = (GLOBAL_NAMESPACE, USER_NAMESPACE, GROUP_NAMESPACE)


ParsedParam = namedtuple('ParsedParam', ['namespace', 'variable'])


def get_parsed_params(message_template):
    """
    Given a message template - extracts the relevant parsed params.

    Raises an InvalidParameterException if any parameters aren't in the right format.
    """
    return [parse_param(param) for param in extract_params(message_template)]


def validate(message_template):
    # convenience method
    get_parsed_params(message_template)


def extract_params(message_template):
    """
    Given a message template - extracts the relevant params.
    """
    return [parsed[1] for parsed in Formatter().parse(message_template) if parsed[1]]


def validate_params(params):
    for param in params:
        parse_param(param)


def parse_param(param):
    """
    Parses a parameter. Raises an InvalidParameterException if the parameter
    is not in a valid format.
    """
    if not param:
        raise InvalidParameterException(_('Empty parameters are not allowed!'))

    if re.search('\s', param):
        raise InvalidParameterException(_('Sorry, no whitespace in parameters is allowed at this time.'))

    split = param.split('.')
    if len(split) > 2:
        raise InvalidParameterException(_('Parameters can have at most one period.'))
    if len(split) == 2:
        namespace, variable = split
    else:
        namespace = GLOBAL_NAMESPACE
        variable = split[0]

    if namespace not in VALID_NAMESPACES:
        raise InvalidParameterException(_('Namespace {} for variable {} is not valid! Must be one of {}.'.format(
            namespace, param, ', '.join(VALID_NAMESPACES)
        )))
    return ParsedParam(namespace, variable)
