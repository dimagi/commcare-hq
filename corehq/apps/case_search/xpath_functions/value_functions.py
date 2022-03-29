import datetime

import pytz
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

from eulxml.xpath.ast import serialize

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.domain.models import Domain
from dimagi.utils.parsing import ISO_DATE_FORMAT


def date(domain, node):
    from corehq.apps.case_search.dsl_utils import unwrap_value

    assert node.name == 'date'
    if len(node.args) != 1:
        raise XPathFunctionException(
            _("The \"date\" function only accepts a single argument"),
            serialize(node)
        )
    arg = node.args[0]

    arg = unwrap_value(domain, arg)

    if isinstance(arg, int):
        return (datetime.date(1970, 1, 1) + datetime.timedelta(days=arg)).strftime("%Y-%m-%d")

    if isinstance(arg, str):
        try:
            parsed_date = parse_date(arg)
        except ValueError:
            raise XPathFunctionException(_("{} is not a valid date").format(arg), serialize(node))

        if parsed_date is None:
            raise XPathFunctionException(
                _("The \"date\" function only accepts strings of the format \"YYYY-mm-dd\""),
                serialize(node)
            )

        return arg

    raise XPathFunctionException(
        "The \"date\" function only accepts integers or strings of the format \"YYYY-mm-dd\"",
        serialize(node)
    )


def today(domain, node):
    assert node.name == 'today'
    if len(node.args) != 0:
        raise XPathFunctionException(
            _("The \"today\" function does not accept any arguments"),
            serialize(node)
        )

    domain_obj = Domain.get_by_name(domain)
    timezone = domain_obj.get_default_timezone() if domain_obj else pytz.UTC
    return datetime.datetime.now(timezone).strftime(ISO_DATE_FORMAT)
