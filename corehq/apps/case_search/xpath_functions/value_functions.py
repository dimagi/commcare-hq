import datetime
import json

from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext as _

import pytz
from dateutil.relativedelta import relativedelta
from eulxml.xpath.ast import serialize

from dimagi.utils.parsing import ISO_DATE_FORMAT

from corehq.apps.case_search.dsl_utils import unwrap_value
from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.domain.models import Domain

from .utils import confirm_args_count


def date(node, context):
    """Coerce the arg to a valid datestring

    Integers are interpreted as days since Jan 1, 1970
      date('2021-01-01') => '2021-01-01'
      date(5) => '1970-01-06'
    """
    assert node.name == 'date'
    confirm_args_count(node, 1)
    arg = node.args[0]

    arg = unwrap_value(arg, context)

    parsed_date = value_to_date(node, arg)
    return parsed_date.strftime(ISO_DATE_FORMAT)


def value_to_date(node, value):
    if isinstance(value, int):
        parsed_date = datetime.date(1970, 1, 1) + datetime.timedelta(days=value)
    elif isinstance(value, str):
        try:
            parsed_date = parse_date(value)
        except ValueError:
            raise XPathFunctionException(_("{} is not a valid date").format(value), serialize(node))
    elif isinstance(value, datetime.date):
        parsed_date = value
    else:
        parsed_date = None

    if parsed_date is None:
        raise XPathFunctionException(
            _("Invalid date value. Dates must be an integer or a string of the format \"YYYY-mm-dd\""),
            serialize(node)
        )

    return parsed_date


def datetime_(node, context):
    """Coerce the arg is a valid IS0 8601 datetime string

    Numeric values are interpreted as days since Jan 1, 1970
    """
    assert node.name == 'datetime'
    confirm_args_count(node, 1)
    arg = node.args[0]
    arg = unwrap_value(arg, context)
    parsed_date = _value_to_datetime(node, arg)
    return parsed_date.isoformat()


def _value_to_datetime(node, value):
    if isinstance(value, (int, float)):
        parsed_dt = datetime.datetime(1970, 1, 1) + datetime.timedelta(days=value)
    elif isinstance(value, str):
        try:
            parsed_dt = parse_datetime(value)
        except ValueError:
            raise XPathFunctionException(_("{} is not a valid datetime").format(value), serialize(node))
    elif isinstance(value, datetime.datetime):
        parsed_dt = value
    else:
        parsed_dt = None

    if parsed_dt is None:
        raise XPathFunctionException(
            _("Invalid datetime value. Must be a number or a ISO 8601 string."),
            serialize(node)
        )

    return parsed_dt.astimezone(pytz.UTC)


def today(node, context):
    """today() => '2024-11-20'"""
    assert node.name == 'today'

    confirm_args_count(node, 0)

    domain_obj = Domain.get_by_name(context.domain)
    timezone = domain_obj.get_default_timezone() if domain_obj else pytz.UTC
    return datetime.datetime.now(timezone).strftime(ISO_DATE_FORMAT)


def now(node, context):
    """now() => '2024-11-20T20:16:29.422120+00:00'"""
    assert node.name == 'now'
    confirm_args_count(node, 0)
    return datetime.datetime.now(pytz.UTC).isoformat()


def date_add(node, context):
    """Add a time interval to an input date

        date-add('2022-01-01', 'days', -1) => '2021-12-31'
        date-add('2020-03-31', 'weeks', 4) => '2020-04-28'
        date-add('2020-04-30', 'months', -2) => '2020-02-29'
        date-add('2020-02-29', 'years', 1) => '2021-02-28'

    Valid intervals are seconds, minutes, hours, days, weeks, months, years
    """
    assert node.name == 'date-add'
    result = _date_or_datetime_add(node, context, value_to_date)
    return result.strftime(ISO_DATE_FORMAT)


def datetime_add(node, context):
    """Same as date-add, but with datetimes"""
    assert node.name == 'datetime-add'
    result = _date_or_datetime_add(node, context, _value_to_datetime)
    return result.isoformat()


def _date_or_datetime_add(node, context, converter_fn):
    confirm_args_count(node, 3)
    date_arg = unwrap_value(node.args[0], context)
    date_value = converter_fn(node, date_arg)

    timedelta = _get_timedelta(
        node,
        unwrap_value(node.args[1], context),
        unwrap_value(node.args[2], context),
    )
    try:
        return date_value + timedelta
    except Exception as e:
        # catchall in case of an unexpected error
        raise XPathFunctionException(str(e), serialize(node))


def _get_timedelta(node, interval_type, quantity):
    interval_types = ("seconds", "minutes", "hours", "days", "weeks", "months", "years")
    if interval_type not in interval_types:
        raise XPathFunctionException(
            _("The \"date-add\" function expects the 'interval' argument to be one of {types}").format(
                types=interval_types
            ),
            serialize(node)
        )

    if isinstance(quantity, str):
        try:
            quantity = float(quantity)
        except (ValueError, TypeError):
            raise XPathFunctionException(
                _("The \"date-add\" function expects the interval quantity to be a numeric value"),
                serialize(node)
            )

    if not isinstance(quantity, (int, float)):
        raise XPathFunctionException(
            _("The \"date-add\" function expects the interval quantity to be a numeric value"),
            serialize(node)
        )

    if interval_type in ("years", "months") and int(quantity) != quantity:
        raise XPathFunctionException(
            _("Non-integer years and months are ambiguous and not supported by the \"date-add\" function"),
            serialize(node)
        )

    return relativedelta(**{interval_type: quantity})


def unwrap_list(node, context):
    assert node.name == 'unwrap-list'
    confirm_args_count(node, 1)

    value = node.args[0]
    return json.loads(value)


def double(node, context):
    """Coerce the argument to a float where possible

    Mirrors the CommCare XPath function `double`. Dates and datetimes are
    converted to days since Jan 1, 1970.
    """
    assert node.name == 'double'
    confirm_args_count(node, 1)
    value = unwrap_value(node.args[0], context)

    if isinstance(value, str):
        try:
            parsed_date = parse_date(value)
        except ValueError:
            parsed_date = None
        if parsed_date:
            return float((parsed_date - datetime.date(1970, 1, 1)).days)

        try:
            parsed_datetime = parse_datetime(value)
        except ValueError:
            parsed_datetime = None
        if parsed_datetime:
            elapsed = parsed_datetime - datetime.datetime(1970, 1, 1, tzinfo=pytz.UTC)
            return elapsed.total_seconds() / (24 * 3600)

    try:
        return float(value)
    except (ValueError, TypeError):
        raise XPathFunctionException(_("Cannot convert {} to a double").format(value), serialize(node))
