from .query_functions import not_
from .subcase_functions import subcase
from .value_functions import date  # noqa: F401

# functions that transform a value
XPATH_VALUE_FUNCTIONS = {
    'date': date,
}


XPATH_QUERY_FUNCTIONS = {
    'not': not_,
    'subcase-exists': subcase,
    'subcase-count': subcase,
}
