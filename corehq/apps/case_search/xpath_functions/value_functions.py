import datetime

from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

import pytz
from dateutil.relativedelta import relativedelta
from eulxml.xpath.ast import serialize

from dimagi.utils.parsing import ISO_DATE_FORMAT

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.domain.models import Domain


def date(node, context):
    from corehq.apps.case_search.dsl_utils import unwrap_value

    assert node.name == 'date'
    if len(node.args) != 1:
        raise XPathFunctionException(
            _("The \"date\" function only accepts a single argument"),
            serialize(node)
        )
    arg = node.args[0]

    arg = unwrap_value(arg, context)

    parsed_date = _value_to_date(node, arg)
    return parsed_date.strftime(ISO_DATE_FORMAT)


def _value_to_date(node, value):
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


def today(node, context):
    assert node.name == 'today'
    if len(node.args) != 0:
        raise XPathFunctionException(
            _("The \"today\" function does not accept any arguments"),
            serialize(node)
        )

    domain_obj = Domain.get_by_name(context.domain)
    timezone = domain_obj.get_default_timezone() if domain_obj else pytz.UTC
    return datetime.datetime.now(timezone).strftime(ISO_DATE_FORMAT)


def date_add(node, context):
    from corehq.apps.case_search.dsl_utils import unwrap_value

    assert node.name == 'date_add'
    if len(node.args) != 3:
        raise XPathFunctionException(
            _("The \"date_add\" function expects three arguments, got {count}").format(count=len(node.args)),
            serialize(node)
        )

    date_arg = unwrap_value(node.args[0], context)
    date_value = _value_to_date(node, date_arg)

    interval_type = unwrap_value(node.args[1], context)
    interval_types = ("days", "weeks", "months", "years")
    if interval_type not in interval_types:
        raise XPathFunctionException(
            _("The \"date_add\" function expects the 'interval' argument to be one of {types}").format(
                types=interval_types
            ),
            serialize(node)
        )

    quantity = unwrap_value(node.args[2], context)
    if isinstance(quantity, str):
        try:
            quantity = float(quantity)
        except (ValueError, TypeError):
            raise XPathFunctionException(
                _("The \"date_add\" function expects the interval quantity to be a numeric value"),
                serialize(node)
            )

    if not isinstance(quantity, (int, float)):
        raise XPathFunctionException(
            _("The \"date_add\" function expects the interval quantity to be a numeric value"),
            serialize(node)
        )

    try:
        result = date_value + relativedelta(**{interval_type: quantity})
    except ValueError as e:
        raise XPathFunctionException(str(e), serialize(node))

    return result.strftime(ISO_DATE_FORMAT)
