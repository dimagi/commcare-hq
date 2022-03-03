from .subcase_functions import subcase
from .value_functions import date, XPathFunctionException  # noqa: F401

# functions that transform a value
XPATH_VALUE_FUNCTIONS = {
    'date': date,
}


XPATH_QUERY_FUNCTIONS = {
    'subcase_exists': subcase,
    'subcase_count': subcase,
}
