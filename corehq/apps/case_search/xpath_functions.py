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


def selected(node, fuzzy):
    if len(node.args) != 2:
        raise XPathFunctionException(_("The \"selected\" function accepts exactly two arguments."))
    property_name = serialize(node.args[0])
    search_values = node.args[1]
    search_mode = None
    if 1 < len(search_values.split(' ')):
        search_mode = 'OR'  # This will actually make the query the same as with selected_any
    return case_property_query(property_name, search_values, fuzzy=fuzzy, mode=search_mode)


def selected_any(node, fuzzy):
    if len(node.args) != 2:
        raise XPathFunctionException(_("The \"selected-any\" function accepts exactly two arguments."))
    property_name = serialize(node.args[0])
    search_values = node.args[1]
    return case_property_query(property_name, search_values, fuzzy=fuzzy, mode='OR')


def selected_all(node, fuzzy):
    if len(node.args) != 2:
        raise XPathFunctionException(_("The \"selected-all\" function accepts exactly two arguments."))
    property_name = serialize(node.args[0])
    search_values = node.args[1]
    return case_property_query(property_name, search_values, fuzzy=fuzzy, mode='AND')


XPATH_VALUE_FUNCTIONS = {
    'date': date,
}

XPATH_QUERY_FUNCTIONS = {
    'selected': selected,
    'selected-any': selected_any,
    'selected-all': selected_all,
}
