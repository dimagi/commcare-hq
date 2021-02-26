from dimagi.utils.parsing import FALSE_STRINGS

from corehq.apps.es import case_search
from corehq.apps.es import cases as case_es

from .core import UserError, serialize_es_case

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 5000


def _to_int(val, param_name):
    try:
        return int(val)
    except ValueError:
        raise UserError(f"'{val}' is not a valid value for '{param_name}'")


FILTERS = {
    'external_id': case_search.external_id,
    'case_type': case_es.case_type,
    'owner_id': case_es.owner,
    'case_name': case_es.case_name,
    'closed': lambda val: case_es.is_closed(_to_boolean(val)),
    # last_modified_start
    # last_modified_end
    # server_last_modified_start
    # server_last_modified_end
    # date_opened_start
    # date_opened_end
    # date_closed_start
    # date_closed_end
}


def get_list(domain, params):
    start = _to_int(params.pop('offset', 0), 'offset')
    page_size = _to_int(params.pop('limit', DEFAULT_PAGE_SIZE), 'limit')
    if page_size > MAX_PAGE_SIZE:
        raise UserError(f"You cannot request more than {MAX_PAGE_SIZE} cases per request.")

    query = (case_search.CaseSearchES()
             .domain(domain)
             .size(page_size)
             .start(start)
             .sort("@indexed_on"))

    for k, v in params.items():
        if k not in FILTERS:
            raise UserError(f"'{k}' is not a valid parameter.")
        query = query.filter(FILTERS[k](v))

    return [serialize_es_case(case) for case in query.run().hits]


def _to_boolean(val):
    return val.lower() not in [''] + list(FALSE_STRINGS)
