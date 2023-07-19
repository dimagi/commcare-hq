from datetime import datetime, timedelta

from django.utils.translation import gettext
from eulxml.xpath import serialize
from eulxml.xpath.ast import Step

from corehq.apps.case_search.dsl_utils import unwrap_value
from corehq.apps.case_search.exceptions import CaseFilterError, XPathFunctionException
from corehq.apps.case_search.xpath_functions.value_functions import value_to_date
from corehq.apps.case_search.const import RANGE_OP_MAPPING, EQ, NEQ
from corehq.apps.es import filters
from corehq.apps.es.case_search import case_property_query, case_property_range_query
from corehq.util.timezones.utils import get_timezone_for_domain
from corehq.util.timezones.conversions import UserTime


def property_comparison_query(context, case_property_name_raw, op, value_raw, node):
    if not isinstance(case_property_name_raw, Step):
        raise CaseFilterError(
            gettext("We didn't understand what you were trying to do with {}").format(serialize(node)),
            serialize(node)
        )

    case_property_name = serialize(case_property_name_raw)
    value = unwrap_value(value_raw, context)
    # adjust the user's input date based on project timezones
    is_user_input = False
    try:
        # this might be inconsistent in daylight savings situations
        value = adjust_input_date_by_timezone(value_to_date(node, value),
                                              get_timezone_for_domain(context.domain), op)
        is_user_input = True
    except (XPathFunctionException, AssertionError):
        # AssertionError is caused by tests that use domains without a valid timezone (in get_timezeone_for_domain)
        pass
    if op in [EQ, NEQ]:
        query = case_property_query(case_property_name, value, fuzzy=context.fuzzy)
        if op == NEQ:
            query = filters.NOT(query)
        return query
    else:
        try:
            return case_property_range_query(case_property_name, is_user_input=is_user_input,
                                             **{RANGE_OP_MAPPING[op]: value})
        except (TypeError, ValueError):
            raise CaseFilterError(
                gettext("The right hand side of a comparison must be a number or date. "
                  "Dates must be surrounded in quotation marks"),
                serialize(node),
            )


def adjust_input_date_by_timezone(date, timezone, op):
    date = datetime.combine(date, datetime.min.time())
    if op == '>' or op == '<=':
        date += timedelta(days=1)
    return UserTime(date, tzinfo=timezone).server_time().done().isoformat()
