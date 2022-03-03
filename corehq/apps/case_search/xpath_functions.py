import datetime

from django.utils.dateparse import parse_date
from django.utils.translation import ugettext as _

from corehq.apps.es.case_search import case_property_query
from eulxml.xpath.ast import serialize


class XPathFunctionException(Exception):
    pass


def date(node):
    assert node.name == 'date'
    if len(node.args) != 1:
        raise XPathFunctionException(_("The \"date\" function only accepts a single argument"))
    arg = node.args[0]

    if isinstance(arg, int):
        return (datetime.date(1970, 1, 1) + datetime.timedelta(days=arg)).strftime("%Y-%m-%d")

    if isinstance(arg, str):
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


def _selected_query(node, fuzzy, operator):
    if len(node.args) != 2:
        raise XPathFunctionException(_(f"The {node.name} function accepts exactly two arguments."))
    property_name = serialize(node.args[0])
    search_values = node.args[1]
    return case_property_query(property_name, search_values, fuzzy=fuzzy, mode=operator)


def selected(node, fuzzy):
    return _selected_query(node, fuzzy=fuzzy, operator='or')


def selected_any(node, fuzzy):
    return _selected_query(node, fuzzy=fuzzy, operator='or')


def selected_all(node, fuzzy):
    return _selected_query(node, fuzzy=fuzzy, operator='and')


XPATH_VALUE_FUNCTIONS = {
    'date': date,
}

XPATH_QUERY_FUNCTIONS = {
    'selected': selected,
    'selected-any': selected_any,
    'selected-all': selected_all,
}
