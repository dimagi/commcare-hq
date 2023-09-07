import datetime
import json

from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

import pytz
from dateutil.relativedelta import relativedelta
from eulxml.xpath.ast import serialize

from dimagi.utils.parsing import ISO_DATE_FORMAT

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.domain.models import Domain

from .utils import confirm_args_count


def date(node, context):
    from corehq.apps.case_search.dsl_utils import unwrap_value

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


def today(node, context):
    assert node.name == 'today'

    confirm_args_count(node, 0)

    domain_obj = Domain.get_by_name(context.domain)
    timezone = domain_obj.get_default_timezone() if domain_obj else pytz.UTC
    return datetime.datetime.now(timezone).strftime(ISO_DATE_FORMAT)


def date_add(node, context):
    from corehq.apps.case_search.dsl_utils import unwrap_value

    assert node.name == 'date-add'

    confirm_args_count(node, 3)

    date_arg = unwrap_value(node.args[0], context)
    date_value = value_to_date(node, date_arg)

    interval_type = unwrap_value(node.args[1], context)
    interval_types = ("days", "weeks", "months", "years")
    if interval_type not in interval_types:
        raise XPathFunctionException(
            _("The \"date-add\" function expects the 'interval' argument to be one of {types}").format(
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

    try:
        result = date_value + relativedelta(**{interval_type: quantity})
    except Exception as e:
        # catchall in case of an unexpected error
        raise XPathFunctionException(str(e), serialize(node))

    return result.strftime(ISO_DATE_FORMAT)


def unwrap_list(node, context):
    assert node.name == 'unwrap-list'
    confirm_args_count(node, 1)

    value = node.args[0]
    return json.loads(value)
