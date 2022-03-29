from django.utils.translation import gettext as _

from eulxml.xpath import serialize
from eulxml.xpath.ast import Step

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.es import filters
from corehq.apps.es.case_search import case_property_query


def not_(domain, node, fuzzy):
    from corehq.apps.case_search.filter_dsl import build_filter_from_ast

    if len(node.args) != 1:
        raise XPathFunctionException(
            _("The \"not\" function only accepts a single argument"),
            serialize(node)
        )
    return filters.NOT(build_filter_from_ast(domain, node.args[0], fuzzy))


def selected_any(domain, node, fuzzy):
    return _selected_query(node, fuzzy=fuzzy, operator='or')


def selected_all(domain, node, fuzzy):
    return _selected_query(node, fuzzy=fuzzy, operator='and')


def _selected_query(node, fuzzy, operator):
    if len(node.args) != 2:
        raise XPathFunctionException(
            _("The {name} function accepts exactly two arguments.").format(name=node.name),
            serialize(node)
        )
    property_name = node.args[0]
    if isinstance(property_name, Step):
        property_name = serialize(property_name)
    elif not isinstance(property_name, str):
        raise XPathFunctionException(
            _("The first argument to '{name}' must be a valid case property name").format(name=node.name),
            serialize(node)
        )
    search_values = node.args[1]
    return case_property_query(property_name, search_values, fuzzy=fuzzy, multivalue_mode=operator)
