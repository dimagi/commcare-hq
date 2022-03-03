from .query_functions import _not
from .subcase_functions import subcase
from .value_functions import XPathFunctionException, date  # noqa: F401

# functions that transform a value
XPATH_VALUE_FUNCTIONS = {
    'date': date,
}


XPATH_QUERY_FUNCTIONS = {
    'not': _not,
    'subcase-exists': subcase,
    'subcase-count': subcase,
}
