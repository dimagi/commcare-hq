from django.utils.translation import gettext as _

from eulxml.xpath.ast import FunctionCall, UnaryExpression, serialize

from corehq.apps.case_search.exceptions import (
    CaseFilterError,
    XPathFunctionException,
)
from corehq.apps.case_search.xpath_functions import XPATH_VALUE_FUNCTIONS


def unwrap_value(value, context):
    """Returns the value of the node if it is wrapped in a function, otherwise just returns the node
    """
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UnaryExpression) and value.op == '-':
        return -1 * value.right
    if not isinstance(value, FunctionCall):
        return value
    try:
        return XPATH_VALUE_FUNCTIONS[value.name](value, context)
    except KeyError:
        raise CaseFilterError(
            _("We don't know what to do with the function \"{}\". Accepted functions are: {}").format(
                value.name,
                ", ".join(list(XPATH_VALUE_FUNCTIONS.keys())),
            ),
            serialize(value)
        )
    except XPathFunctionException as e:
        raise CaseFilterError(str(e), serialize(value))
