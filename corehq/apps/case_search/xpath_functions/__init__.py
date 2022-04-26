from .query_functions import not_, selected_all, selected_any, within_distance
from .subcase_functions import subcase
from .value_functions import date, date_add, today

# functions that transform or produce a value
XPATH_VALUE_FUNCTIONS = {
    'date': date,
    'date-add': date_add,
    'today': today,
}


XPATH_QUERY_FUNCTIONS = {
    'not': not_,
    'subcase-exists': subcase,
    'subcase-count': subcase,
    'selected': selected_any,  # selected and selected_any function identically.
    'selected-any': selected_any,
    'selected-all': selected_all,
    'within-distance': within_distance,
}
