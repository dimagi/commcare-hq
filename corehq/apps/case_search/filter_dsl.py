import re
from dataclasses import dataclass
from typing import Union, List

from django.utils.translation import gettext as _
from eulxml.xpath import parse as parse_xpath
from eulxml.xpath.ast import (
    BinaryExpression,
    FunctionCall,
    serialize,
)

import corehq
from corehq.apps.case_search.const import OPERATOR_MAPPING, COMPARISON_OPERATORS, ALL_OPERATORS
from corehq.apps.case_search.exceptions import (
    CaseFilterError,
    XPathFunctionException,
)
from corehq.apps.case_search.xpath_functions import (
    XPATH_QUERY_FUNCTIONS,
)
from corehq.apps.case_search.xpath_functions.ancestor_functions import is_ancestor_comparison, \
    ancestor_comparison_query
from corehq.apps.case_search.xpath_functions.comparison import property_comparison_query


@dataclass
class SearchFilterContext:
    domain: Union[str, List[str]]  # query domain
    fuzzy: bool = False
    request_domain: str = None
    profiler: 'corehq.apps.case_search.utils.CaseSearchProfiler' = None

    def __post_init__(self):
        from corehq.apps.case_search.utils import CaseSearchProfiler
        if self.request_domain is None:
            if isinstance(self.domain, str):
                self.request_domain = self.domain
            elif len(self.domain) == 1:
                self.request_domain = self.domain[0]
            else:
                raise ValueError("When domain is a list with more than one item, request_domain cannot be None.")
        if self.profiler is None:
            self.profiler = CaseSearchProfiler()


def print_ast(node):
    """Prints the AST provided by eulxml.xpath.parse

    Useful for debugging particular expressions
    """
    def visit(node, indent):
        print("\t" * indent, node)  # noqa

        if hasattr(node, 'left'):
            indent += 1
            visit(node.left, indent)

        if hasattr(node, 'op'):
            print("\t" * indent, "##### {} #####".format(node.op))  # noqa

        if hasattr(node, 'right'):
            visit(node.right, indent)
            indent -= 1

    visit(node, 0)


def build_filter_from_ast(node, context):
    """Builds an ES filter from an AST provided by eulxml.xpath.parse

    If fuzzy is true, all equality operations will be treated as fuzzy.
    """
    def _simple_ancestor_query(node):
        return ancestor_comparison_query(context, node)

    def _is_subcase_count(node):
        """Returns whether a particular AST node is a subcase lookup.
        This is needed for subcase-count since we need the full expression, not just the function."""
        if not isinstance(node, BinaryExpression):
            return False

        return isinstance(node.left, FunctionCall) and node.left.name == 'subcase-count'

    def _comparison(node):
        """Returns the filter for a comparison operation (=, !=, >, <, >=, <=)

        """
        return property_comparison_query(context, node.left, node.op, node.right, node)

    def visit(node):

        if isinstance(node, FunctionCall):
            if node.name in XPATH_QUERY_FUNCTIONS:
                return XPATH_QUERY_FUNCTIONS[node.name](node, context)
            else:
                raise XPathFunctionException(
                    _("'{name}' is not a valid standalone function").format(name=node.name),
                    serialize(node)
                )

        if not hasattr(node, 'op'):
            raise CaseFilterError(
                _("Your search query is required to have at least one boolean operator ({boolean_ops})").format(
                    boolean_ops=", ".join(COMPARISON_OPERATORS),
                ),
                serialize(node)
            )

        if is_ancestor_comparison(node):
            # this node represents a filter on a property for a related case
            return _simple_ancestor_query(node)

        if _is_subcase_count(node):
            return XPATH_QUERY_FUNCTIONS['subcase-count'](node, context)

        if node.op in COMPARISON_OPERATORS:
            # This node is a leaf
            return _comparison(node)

        if node.op in list(OPERATOR_MAPPING.keys()):
            # This is another branch in the tree
            return OPERATOR_MAPPING[node.op](visit(node.left), visit(node.right))

        raise CaseFilterError(
            _("We don't know what to do with operator '{}'. Please try reformatting your query.".format(node.op)),
            serialize(node)
        )

    return visit(node)


def build_filter_from_xpath(query_domain, xpath, fuzzy=False, request_domain=None, profiler=None):
    """Given an xpath expression this function will generate an Elasticsearch
    filter"""
    error_message = _(
        "We didn't understand what you were trying to do with {}. "
        "Please try reformatting your query. "
        "The operators we accept are: {}"
    )
    context = SearchFilterContext(query_domain, fuzzy, request_domain, profiler)
    try:
        return build_filter_from_ast(parse_xpath(xpath), context)
    except TypeError as e:
        text_error = re.search(r"Unknown text '(.+)'", str(e))
        if text_error:
            # This often happens if there is a bad operator (e.g. a ~ b)
            bad_part = text_error.groups()[0]
            raise CaseFilterError(error_message.format(bad_part, ", ".join(ALL_OPERATORS)), bad_part)
        raise CaseFilterError(_("Malformed search query"), None)
    except RuntimeError as e:
        # eulxml passes us string errors from YACC
        lex_token_error = re.search(r"LexToken\((\w+),\w?'(.+)'", str(e))
        if lex_token_error:
            bad_part = lex_token_error.groups()[1]
            raise CaseFilterError(error_message.format(bad_part, ", ".join(ALL_OPERATORS)), bad_part)
        raise CaseFilterError(_("Malformed search query"), None)
