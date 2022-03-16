import datetime

from django.utils.dateparse import parse_date
from django.utils.translation import ugettext as _

from eulxml.xpath.ast import serialize

from corehq.apps.case_search.exceptions import XPathFunctionException


def date(node):
    assert node.name == 'date'
    if len(node.args) != 1:
        raise XPathFunctionException(
            _("The \"date\" function only accepts a single argument"),
            serialize(node)
        )
    arg = node.args[0]

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
