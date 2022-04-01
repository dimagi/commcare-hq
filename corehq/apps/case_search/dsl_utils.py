from django.utils.translation import gettext as _

from eulxml.xpath.ast import FunctionCall, UnaryExpression, serialize

from corehq.apps.case_search.exceptions import (
    CaseFilterError,
    XPathFunctionException,
)
from corehq.apps.case_search.xpath_functions import XPATH_VALUE_FUNCTIONS


def unwrap_value(domain, node):
    """Returns the value of the node if it is wrapped in a function, otherwise just returns the node
    """
    if isinstance(node, (str, int, float, bool)):
        return node
    if isinstance(node, UnaryExpression) and node.op == '-':
        return -1 * node.right
    if not isinstance(node, FunctionCall):
        return node
    try:
        return XPATH_VALUE_FUNCTIONS[node.name](domain, node)
    except KeyError:
        raise CaseFilterError(
            _("We don't know what to do with the function \"{}\". Accepted functions are: {}").format(
                node.name,
                ", ".join(list(XPATH_VALUE_FUNCTIONS.keys())),
            ),
            serialize(node)
        )
    except XPathFunctionException as e:
        raise CaseFilterError(str(e), serialize(node))
