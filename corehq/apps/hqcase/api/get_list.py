from corehq.apps.es import CaseSearchES

from .core import UserError, serialize_es_case

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 5000


def _to_int(val, param_name):
    try:
        return int(val)
    except ValueError:
        raise UserError(f"'{val}' is not a valid value for '{param_name}'")


# TODO:
# external_id
# case_type
# owner_id
# case_name
# last_modified_by_user_id
# closed
# last_modified_start
# last_modified_end
# server_last_modified_start
# server_last_modified_end
# date_opened_start
# date_opened_end
# date_closed_start
# date_closed_end


def get_list(domain, params):
    start = _to_int(params.pop('offset', 0), 'offset')
    page_size = _to_int(params.pop('limit', DEFAULT_PAGE_SIZE), 'limit')
    if page_size > MAX_PAGE_SIZE:
        raise UserError(f"You cannot request more than {MAX_PAGE_SIZE} cases per request.")

    query = (CaseSearchES()
             .domain(domain)
             .size(page_size)
             .start(start)
             .sort("@indexed_on"))

    return [serialize_es_case(case) for case in query.run().hits]
