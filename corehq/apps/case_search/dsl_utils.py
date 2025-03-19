from django.utils.translation import gettext as _

from eulxml.xpath.ast import FunctionCall, UnaryExpression, serialize, Step

from corehq.apps.case_search.exceptions import (
    CaseFilterError,
    XPathFunctionException,
)


def unwrap_value(value, context):
    """Returns the value of the node if it is wrapped in a function, otherwise just returns the node
    """
    from corehq.apps.case_search.xpath_functions import XPATH_VALUE_FUNCTIONS
    if isinstance(value, Step):
        raise CaseFilterError(
            _("You cannot reference a case property on the right side "
              "of an operation. If \"{}\" is meant to be a value, please surround it with "
              "quotation marks").format(serialize(value)),
            ""
        )

    acceptable_types = (int, str, float, bool, FunctionCall, UnaryExpression)
    if not isinstance(value, acceptable_types):
        raise CaseFilterError(_("Unexpected type for value expression"), serialize(value))

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
