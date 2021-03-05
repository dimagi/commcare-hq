import datetime
from collections import defaultdict
from functools import partial

from attr import attrib, attrs, fields_dict
from dateutil.parser import parse

from dimagi.utils.parsing import FALSE_STRINGS

from corehq.apps.es import case_search
from corehq.apps.es import cases as case_es

from .core import UserError, serialize_es_case

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 5000
CASE_PROPERTY_PREFIX = 'property'
UNDEFINED = object()


def _to_ternary(val):
    """True, False, or Undefined"""
    if val is UNDEFINED:
        return val
    return not (val == '' or val.lower() in FALSE_STRINGS)


def _to_int(val, param):
    try:
        return int(val)
    except ValueError:
        raise UserError(f"'{val}' is not a valid value for '{param}'")


def _to_date_or_datetime(val):
    try:
        # If it's only a date, don't turn it into a datetime
        return datetime.datetime.strptime(val, '%Y-%m-%d').date()
    except ValueError:
        try:
            return parse(val)
        except ValueError:
            raise UserError(f"Cannot parse datetime '{val}'")


def _to_date_range(vals):
    if vals is UNDEFINED:
        return vals
    ret = {}
    for k, v in vals.items():
        if k not in ('gt', 'gte', 'lte', 'lt'):
            raise UserError(f"{k} is not a valid date parameter")
        ret[k] = _to_date_or_datetime(v)
    return ret


FILTERS = {
    'external_id': case_search.external_id,
    'case_type': case_es.case_type,
    'owner_id': case_es.owner,
    'case_name': case_es.case_name,
    'closed': case_es.is_closed,
    'last_modified': lambda val: case_es.modified_range(**val),
    'server_last_modified': lambda val: case_es.server_modified_range(**val),
    'date_opened': lambda val: case_es.opened_range(**val),
    'date_closed': lambda val: case_es.closed_range(**val),
}


def date_range_attrib():
    return attrib(
        default=UNDEFINED,
        converter=_to_date_range,
        metadata={'is_compound': True}
    )


@attrs()
class CaseListParams:
    offset = attrib(default=0, converter=partial(_to_int, param='offset'))
    limit = attrib(default=DEFAULT_PAGE_SIZE, converter=partial(_to_int, param='limit'))
    external_id = attrib(default=UNDEFINED)
    case_type = attrib(default=UNDEFINED)
    owner_id = attrib(default=UNDEFINED)
    case_name = attrib(default=UNDEFINED)
    last_modified = date_range_attrib()
    server_last_modified = date_range_attrib()
    date_opened = date_range_attrib()
    date_closed = date_range_attrib()
    closed = attrib(default=UNDEFINED, converter=_to_ternary)
    property = attrib(factory=dict, metadata={'is_compound': True})

    @classmethod
    def from_querydict(cls, querydict):
        vals_by_field = defaultdict(dict)
        for key, val in querydict.items():
            if '.' in key:
                field_name, param = key.split('.', maxsplit=1)
                if not cls._is_compound(field_name):
                    raise UserError(f"'{key}' is not a valid parameter.")
                vals_by_field[field_name][param] = val
            else:
                if cls._is_compound(key):
                    raise UserError(f"'{key}' is not a valid parameter.")
                vals_by_field[key] = val

        fields = fields_dict(cls)
        if any(field not in fields for field in vals_by_field):
            raise UserError(f"'{key}' is not a valid parameter.")

        return CaseListParams(**vals_by_field)

    @classmethod
    def _is_compound(cls, field_name):
        fields = fields_dict(cls)
        return field_name in fields and fields[field_name].metadata.get('is_compound', False)

    @limit.validator
    def validate_page_size(self, attribute, value):
        if value > MAX_PAGE_SIZE:
            raise UserError(f"You cannot request more than {MAX_PAGE_SIZE} cases per request.")


def get_list(domain, querydict):
    params = CaseListParams.from_querydict(querydict)

    query = (case_search.CaseSearchES()
             .domain(domain)
             .size(params.limit)
             .start(params.offset)
             .sort("@indexed_on"))

    for field, es_filter in FILTERS.items():
        val = getattr(params, field, UNDEFINED)
        if val != UNDEFINED:
            query = query.filter(es_filter(val))

    for prop, val in params.property.items():
        query = query.filter(_get_custom_property_filter(prop, val))

    return [serialize_es_case(case) for case in query.run().hits]


def _get_custom_property_filter(prop, val):
    if val == "":
        return case_search.case_property_missing(prop)
    return case_search.exact_case_property_text_query(prop, val)
