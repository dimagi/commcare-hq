from django.utils.translation import gettext as _

from eulxml.xpath import serialize
from eulxml.xpath.ast import Step

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.es import filters
from corehq.apps.es.case_search import case_property_query

from .utils import confirm_args_count


def not_(node, context):
    from corehq.apps.case_search.filter_dsl import build_filter_from_ast
    confirm_args_count(node, 1)
    return filters.NOT(build_filter_from_ast(node.args[0], context))


def selected_any(node, context):
    return _selected_query(node, context, operator='or')


def selected_all(node, context):
    return _selected_query(node, context, operator='and')


def _selected_query(node, context, operator):
    confirm_args_count(node, 2)

    property_name = node.args[0]
    if isinstance(property_name, Step):
        property_name = serialize(property_name)
    elif not isinstance(property_name, str):
        raise XPathFunctionException(
            _("The first argument to '{name}' must be a valid case property name").format(name=node.name),
            serialize(node)
        )
    search_values = node.args[1]
    return case_property_query(property_name, search_values, fuzzy=context.fuzzy, multivalue_mode=operator)
