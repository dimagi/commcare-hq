from .query_functions import (
    fuzzy_match,
    not_,
    selected_all,
    selected_any,
    within_distance,
    phonetic_match,
    starts_with,
    match_all,
    match_none
)
from .subcase_functions import subcase
from .ancestor_functions import ancestor_exists
from .value_functions import date, date_add, today, unwrap_list

# functions that transform or produce a value
XPATH_VALUE_FUNCTIONS = {
    'date': date,
    'date-add': date_add,
    'today': today,
    'unwrap-list': unwrap_list,
}


XPATH_QUERY_FUNCTIONS = {
    'not': not_,
    'subcase-exists': subcase,
    'subcase-count': subcase,
    'selected': selected_any,  # selected and selected_any function identically.
    'selected-any': selected_any,
    'selected-all': selected_all,
    'within-distance': within_distance,
    'fuzzy-match': fuzzy_match,
    'phonetic-match': phonetic_match,
    'starts-with': starts_with,
    'ancestor-exists': ancestor_exists,
    'match-all': match_all,
    'match-none': match_none,
}
