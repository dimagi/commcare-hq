from __future__ import absolute_import, unicode_literals

import datetime

import six
from django.utils.dateparse import parse_date
from django.utils.translation import ugettext as _

from corehq.util.python_compatibility import soft_assert_type_text


class XPathFunctionException(Exception):
    pass


def date(node):
    assert node.name == 'date'
    if len(node.args) != 1:
        raise XPathFunctionException(_("The \"date\" function only accepts a single argument"))
    arg = node.args[0]

    if isinstance(arg, int):
        return (datetime.date(1970, 1, 1) + datetime.timedelta(days=arg)).strftime("%Y-%m-%d")

    if isinstance(arg, six.string_types):
        soft_assert_type_text(arg)
        try:
            parsed_date = parse_date(arg)
        except ValueError:
            raise XPathFunctionException(_("{} is not a valid date").format(arg))

        if parsed_date is None:
            raise XPathFunctionException(
                _("The \"date\" function only accepts strings of the format \"YYYY-mm-dd\"")
            )

        return arg

    raise XPathFunctionException(
        "The \"date\" function only accepts integers or strings of the format \"YYYY-mm-dd\""
    )


XPATH_FUNCTIONS = {
    'date': date,
}
