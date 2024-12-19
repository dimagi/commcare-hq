from datetime import date, datetime, timedelta

from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext

from eulxml.xpath import serialize
from eulxml.xpath.ast import Step

from corehq.apps.case_search.const import (
    EQ,
    INDEXED_METADATA_BY_KEY,
    NEQ,
    RANGE_OP_MAPPING,
)
from corehq.apps.case_search.dsl_utils import unwrap_value
from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.es import filters
from corehq.apps.es.case_search import (
    case_property_date_range,
    case_property_numeric_range,
    case_property_query,
)
from corehq.toggles import CASE_SEARCH_INDEXED_METADATA
from corehq.util.timezones.conversions import UserTime
from corehq.util.timezones.utils import get_timezone_for_domain


def property_comparison_query(context, case_property_name_raw, op, value_raw, node):
    if not isinstance(case_property_name_raw, Step):
        raise CaseFilterError(
            gettext("We didn't understand what you were trying to do with {}").format(serialize(node)),
            serialize(node)
        )

    case_property_name = serialize(case_property_name_raw)
    value = unwrap_value(value_raw, context)
    if meta_property := INDEXED_METADATA_BY_KEY.get(case_property_name):
        if meta_property.is_datetime:
            return _create_system_datetime_query(
                context.domain, meta_property, op, value, node,
            )
        if (CASE_SEARCH_INDEXED_METADATA.enabled(context.domain)
                and op in [EQ, NEQ] and not context.fuzzy):  # We can filter better at the top level
            return _create_system_query(meta_property, op, value)
    return _create_query(context, case_property_name, op, value, node)


def _create_query(context, case_property_name, op, value, node):
    if op == EQ:
        return case_property_query(case_property_name, value, fuzzy=context.fuzzy)
    if op == NEQ:
        return filters.NOT(_create_query(context, case_property_name, EQ, value, node))
    return _case_property_range_query(case_property_name, op, value, node)


def _case_property_range_query(case_property_name, op, value, node):
    try:
        return case_property_range_query(case_property_name, **{RANGE_OP_MAPPING[op]: value})
    except TypeError:
        raise CaseFilterError(
            gettext("The right hand side of a comparison must be a number or date. "
                "Dates must be surrounded in quotation marks"),
            serialize(node),
        )
    except ValueError as e:
        raise CaseFilterError(str(e), serialize(node))


def case_property_range_query(case_property_name, gt=None, gte=None, lt=None, lte=None):
    """Returns cases where case property `key` fall into the range provided."""
    kwargs = {'gt': gt, 'gte': gte, 'lt': lt, 'lte': lte}
    try:
        # if its a number, use it
        kwargs = {key: float(value) for key, value in kwargs.items() if value is not None}
    except (TypeError, ValueError):
        pass
    else:
        return case_property_numeric_range(case_property_name, **kwargs)

    kwargs = {
        key: value if isinstance(value, (date, datetime)) else _parse_date_or_datetime(value)
        for key, value in kwargs.items()
        if value is not None
    }
    if not kwargs:
        raise TypeError()       # Neither a date nor number was passed in
    return case_property_date_range(case_property_name, **kwargs)


def _parse_date_or_datetime(value):
    parsed_date = _parse_date(value)
    if parsed_date is not None:
        return parsed_date
    parsed_datetime = _parse_datetime(value)
    if parsed_datetime is not None:
        return parsed_datetime
    raise ValueError(gettext(f"{value} is not a correctly formatted date or datetime."))


def _parse_date(value):
    try:
        return parse_date(value)
    except ValueError:
        raise ValueError(gettext(f"{value} is an invalid date."))


def _parse_datetime(value):
    try:
        return parse_datetime(value)
    except ValueError:
        raise ValueError(gettext(f"{value} is an invalid datetime."))


def _create_system_datetime_query(domain, meta_property, op, value, node):
    """
    Given a date, it gets the equivalent starting time of that date in UTC. i.e 2023-06-05
    in Asia/Seoul timezone begins at 2023-06-04T20:00:00 UTC.
    This might be inconsistent in daylight savings situations.
    """
    if op == NEQ:
        return filters.NOT(_create_system_datetime_query(domain, meta_property, EQ, value, node))

    try:
        date_or_datetime = _parse_date_or_datetime(value)
    except ValueError as e:
        raise CaseFilterError(str(e), serialize(node))

    if isinstance(date_or_datetime, datetime):
        if op == EQ:
            return filters.term(meta_property.es_field_name, value)
        range_kwargs = {RANGE_OP_MAPPING[op]: date_or_datetime}
    else:
        timezone = get_timezone_for_domain(domain)
        utc_equivalent_datetime_value = adjust_input_date_by_timezone(date_or_datetime, timezone, op)
        if op == EQ:
            range_kwargs = {
                'gte': utc_equivalent_datetime_value,
                'lt': utc_equivalent_datetime_value + timedelta(days=1),
            }
        else:
            range_kwargs = {RANGE_OP_MAPPING[op]: utc_equivalent_datetime_value}

    if CASE_SEARCH_INDEXED_METADATA.enabled(domain):
        return filters.date_range(meta_property.es_field_name, **range_kwargs)
    return case_property_date_range(meta_property.key, **range_kwargs)


def adjust_input_date_by_timezone(date_, timezone, op):
    date_ = datetime(date_.year, date_.month, date_.day)
    if op == '>' or op == '<=':
        date_ += timedelta(days=1)
    return UserTime(date_, tzinfo=timezone).server_time().done()


def _create_system_query(meta_property, op, value):
    if op == NEQ:
        return filters.NOT(_create_system_query(meta_property, EQ, value))
    if not value:
        return filters.empty(meta_property.es_field_name)
    if meta_property.key == '@status':
        value = value == 'closed'  # "@status = 'closed'" => "closed = True"
    return filters.term(meta_property.es_field_name, value)
