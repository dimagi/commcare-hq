from datetime import datetime
from django.db import models
from django.utils.translation import gettext as _
from eulxml.xpath import serialize

from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES, SPECIAL_CASE_PROPERTIES_MAP
from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.form_processor.models import CommCareCase
from corehq.util.timezones.conversions import UserTime


def confirm_args_count(node, expected):
    actual = len(node.args)
    if actual != expected:
        raise XPathFunctionException(
            _(f"The '{node.name}' function accepts exactly {expected} arguments, got {actual}"),
            serialize(node)
        )


def case_property_requires_timezone_adjustment(case_property_name):
    return (case_property_name in SPECIAL_CASE_PROPERTIES
            and isinstance(SPECIAL_CASE_PROPERTIES_MAP[case_property_name].field_getter(CommCareCase),
            models.DateTimeField))


def adjust_to_utc(date, timezone):
    date = datetime(date.year, date.month, date.day)
    return UserTime(date, tzinfo=timezone).server_time().done()
