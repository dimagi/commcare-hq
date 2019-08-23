from __future__ import absolute_import, print_function, unicode_literals

import re

from django.utils.translation import ugettext as _

import six
from eulxml.xpath import parse as parse_xpath
from eulxml.xpath.ast import FunctionCall, Step, UnaryExpression, serialize
from six import integer_types, string_types

from corehq.apps.case_search.xpath_functions import (
    XPATH_FUNCTIONS,
    XPathFunctionException,
)
from corehq.apps.es import filters
from corehq.apps.es.case_search import (
    CaseSearchES,
    case_property_missing,
    case_property_range_query,
    exact_case_property_text_query,
    reverse_index_case_query,
)


class CaseFilterError(Exception):

    def __init__(self, message, filter_part):
        self.filter_part = filter_part
        super(CaseFilterError, self).__init__(message)


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


MAX_RELATED_CASES = 500000  # Limit each related case lookup to return 500,000 cases to prevent timeouts


OPERATOR_MAPPING = {
    'and': filters.AND,
    'not': filters.NOT,
    'or': filters.OR,
}
COMPARISON_MAPPING = {
    '>': 'gt',
    '>=': 'gte',
    '<': 'lt',
    '<=': 'lte',
}

EQ = "="
NEQ = "!="

ALL_OPERATORS = [EQ, NEQ] + list(OPERATOR_MAPPING.keys()) + list(COMPARISON_MAPPING.keys())


def build_filter_from_ast(domain, node):
    """Builds an ES filter from an AST provided by eulxml.xpath.parse
    """

    def _walk_related_cases(node):
        """Return a query that will fulfill the filter on the related case.

        :param node: a node returned from eulxml.xpath.parse of the form `parent/grandparent/property = 'value'`

        Since ES has no way of performing joins, we filter down in stages:
        1. Find the ids of all cases where the condition is met
        2. Walk down the case hierarchy, finding all related cases with the right identifier to the ids
        found in (1).
        3. Return the lowest of these ids as an related case query filter
        """

        # fetch the ids of the highest level cases that match the case_property
        # i.e. all the cases which have `property = 'value'`
        ids = _parent_property_lookup(node)

        # get the related case path we need to walk, i.e. `parent/grandparent/property`
        n = node.left
        while _is_related_case_lookup(n):
            # This walks down the tree and finds case ids that match each identifier
            # This is basically performing multiple "joins" to find related cases since ES
            # doesn't have a way to relate models together

            # Get the path to the related case, e.g. `parent/grandparent`
            # On subsequent run throughs, it walks down the tree (e.g. n = [parent, /, grandparent])
            n = n.left
            identifier = serialize(n.right)  # the identifier at this step, e.g. `grandparent`

            # get the ids of the cases that point at the previous level's cases
            # this has the potential of being a very large list
            ids = _child_case_lookup(ids, identifier=identifier)
            if not ids:
                break

        # after walking the full tree, get the final level we are interested in, i.e. `parent`
        final_identifier = serialize(n.left)
        return reverse_index_case_query(ids, final_identifier)

    def _parent_property_lookup(node):
        """given a node of the form `parent/foo = 'thing'`, return all case_ids where `foo = thing`
        """
        if isinstance(node.right, Step):
            _raise_step_RHS(node)
        new_query = "{} {} '{}'".format(serialize(node.left.right), node.op, node.right)
        es_query = CaseSearchES().domain(domain).xpath_query(domain, new_query)
        if es_query.count() > MAX_RELATED_CASES:
            raise CaseFilterError(
                _("The related case lookup you are trying to perform would return too many cases"),
                new_query
            )
        return es_query.scroll_ids()

    def _child_case_lookup(case_ids, identifier):
        """returns a list of all case_ids who have parents `case_id` with the relationship `identifier`
        """
        return CaseSearchES().domain(domain).get_child_cases(case_ids, identifier).scroll_ids()

    def _is_related_case_lookup(node):
        """Returns whether a particular AST node is a related case lookup

        e.g. `parent/host/thing = 'foo'`
        """
        return hasattr(node, 'left') and hasattr(node.left, 'op') and node.left.op == '/'

    def _raise_step_RHS(node):
        raise CaseFilterError(
            _("You cannot reference a case property on the right side "
              "of a boolean operation. If \"{}\" is meant to be a value, please surround it with "
              "quotation marks").format(serialize(node.right)),
            serialize(node)
        )

    def _unwrap_function(node):
        """Returns the value of the node if it is wrapped in a function, otherwise just returns the node
        """
        if isinstance(node, UnaryExpression) and node.op == '-':
            return -1 * node.right
        if not isinstance(node, FunctionCall):
            return node
        try:
            return XPATH_FUNCTIONS[node.name](node)
        except KeyError:
            raise CaseFilterError(
                _("We don't know what to do with the function \"{}\". Accepted functions are: {}").format(
                    node.name,
                    ", ".join(list(XPATH_FUNCTIONS.keys())),
                ),
                serialize(node)
            )
        except XPathFunctionException as e:
            raise CaseFilterError(six.text_type(e), serialize(node))

    def _equality(node):
        """Returns the filter for an equality operation (=, !=)

        """
        acceptable_rhs_types = integer_types + (string_types, float, FunctionCall, UnaryExpression)
        if isinstance(node.left, Step) and (
                isinstance(node.right, acceptable_rhs_types)):
            # This is a leaf node
            case_property_name = serialize(node.left)
            value = _unwrap_function(node.right)

            if value == '':
                q = case_property_missing(case_property_name)
            else:
                q = exact_case_property_text_query(case_property_name, value)

            if node.op == '!=':
                return filters.NOT(q)

            return q

        if isinstance(node.right, Step):
            _raise_step_RHS(node)

        raise CaseFilterError(
            _("We didn't understand what you were trying to do with {}").format(serialize(node)),
            serialize(node)
        )

    def _comparison(node):
        """Returns the filter for a comparison operation (>, <, >=, <=)

        """
        try:
            case_property_name = serialize(node.left)
            value = _unwrap_function(node.right)
            return case_property_range_query(case_property_name, **{COMPARISON_MAPPING[node.op]: value})
        except (TypeError, ValueError):
            raise CaseFilterError(
                _("The right hand side of a comparison must be a number or date. "
                  "Dates must be surrounded in quotation marks"),
                serialize(node),
            )

    def visit(node):
        if not hasattr(node, 'op'):
            raise CaseFilterError(
                _("Your search query is required to have at least one boolean operator ({boolean_ops})").format(
                    boolean_ops=", ".join(list(COMPARISON_MAPPING.keys()) + [EQ, NEQ]),
                ),
                serialize(node)
            )

        if _is_related_case_lookup(node):
            # this node represents a filter on a property for a related case
            return _walk_related_cases(node)

        if node.op in [EQ, NEQ]:
            # This node is a leaf
            return _equality(node)

        if node.op in list(COMPARISON_MAPPING.keys()):
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


def build_filter_from_xpath(domain, xpath):
    error_message = _(
        "We didn't understand what you were trying to do with {}. "
        "Please try reformatting your query. "
        "The operators we accept are: {}"
    )
    try:
        return build_filter_from_ast(domain, parse_xpath(xpath))
    except TypeError as e:
        text_error = re.search(r"Unknown text '(.+)'", six.text_type(e))
        if text_error:
            # This often happens if there is a bad operator (e.g. a ~ b)
            bad_part = text_error.groups()[0]
            raise CaseFilterError(error_message.format(bad_part, ", ".join(ALL_OPERATORS)), bad_part)
        raise CaseFilterError(_("Malformed search query"), None)
    except RuntimeError as e:
        # eulxml passes us string errors from YACC
        lex_token_error = re.search(r"LexToken\((\w+),\w?'(.+)'", six.text_type(e))
        if lex_token_error:
            bad_part = lex_token_error.groups()[1]
            raise CaseFilterError(error_message.format(bad_part, ", ".join(ALL_OPERATORS)), bad_part)
        raise CaseFilterError(_("Malformed search query"), None)


def get_properties_from_ast(node):
    """Returns a list of case properties referenced in the XPath expression

    Skips malformed parts of the XPath expression
    """
    columns = set()

    def visit(node):
        if not hasattr(node, 'op'):
            return

        if node.op in ([EQ, NEQ] + list(COMPARISON_MAPPING.keys())):
            columns.add(serialize(node.left))

        if node.op in list(OPERATOR_MAPPING.keys()):
            visit(node.left)
            visit(node.right)

    visit(node)
    return list(columns)


def get_properties_from_xpath(xpath):
    return get_properties_from_ast(parse_xpath(xpath))
