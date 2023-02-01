import re
from dataclasses import dataclass

from django.utils.translation import gettext as _

from eulxml.xpath import parse as parse_xpath
from eulxml.xpath.ast import (
    BinaryExpression,
    FunctionCall,
    Step,
    UnaryExpression,
    serialize,
)

from corehq.apps.case_search.dsl_utils import unwrap_value
from corehq.apps.case_search.exceptions import (
    CaseFilterError,
    TooManyRelatedCasesError,
    XPathFunctionException,
)
from corehq.apps.case_search.xpath_functions import (
    XPATH_QUERY_FUNCTIONS,
)
from corehq.apps.es import filters
from corehq.apps.es.case_search import (
    CaseSearchES,
    case_property_query,
    case_property_range_query,
    reverse_index_case_query,
)


@dataclass
class SearchFilterContext:
    domain: str
    fuzzy: bool = False


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
    'or': filters.OR,
}
RANGE_OP_MAPPING = {
    '>': 'gt',
    '>=': 'gte',
    '<': 'lt',
    '<=': 'lte',
}

EQ = "="
NEQ = "!="
COMPARISON_OPERATORS = [EQ, NEQ] + list(RANGE_OP_MAPPING.keys())

ALL_OPERATORS = COMPARISON_OPERATORS + list(OPERATOR_MAPPING.keys())


def build_filter_from_ast(node, context):
    """Builds an ES filter from an AST provided by eulxml.xpath.parse

    If fuzzy is true, all equality operations will be treated as fuzzy.
    """

    def _walk_ancestor_cases(node):
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
        while _is_ancestor_case_lookup(n):
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
        es_filter = _comparison_raw(node.left.right, node.op, node.right, node)
        es_query = CaseSearchES().domain(context.domain).filter(es_filter)
        if es_query.count() > MAX_RELATED_CASES:
            new_query = '{} {} "{}"'.format(serialize(node.left.right), node.op, node.right)
            raise TooManyRelatedCasesError(
                _("The related case lookup you are trying to perform would return too many cases"),
                new_query
            )

        return es_query.scroll_ids()

    def _child_case_lookup(case_ids, identifier):
        """returns a list of all case_ids who have parents `case_id` with the relationship `identifier`
        """
        return CaseSearchES().domain(context.domain).get_child_cases(case_ids, identifier).scroll_ids()

    def _is_ancestor_case_lookup(node):
        """Returns whether a particular AST node is an ancestory case lookup

        e.g. `parent/host/thing = 'foo'`
        """
        return hasattr(node, 'left') and hasattr(node.left, 'op') and node.left.op == '/'

    def _is_subcase_count(node):
        """Returns whether a particular AST node is a subcase lookup.
        This is needed for subcase-count since we need the full expression, not just the function."""
        if not isinstance(node, BinaryExpression):
            return False

        return isinstance(node.left, FunctionCall) and node.left.name == 'subcase-count'

    def _comparison(node):
        """Returns the filter for a comparison operation (=, !=, >, <, >=, <=)

        """
        return _comparison_raw(node.left, node.op, node.right, node)

    def _comparison_raw(case_property_name_raw, op, value_raw, node):
        if not isinstance(case_property_name_raw, Step):
            raise CaseFilterError(
                _("We didn't understand what you were trying to do with {}").format(serialize(node)),
                serialize(node)
            )

        case_property_name = serialize(case_property_name_raw)
        value = unwrap_value(value_raw, context)
        if op in [EQ, NEQ]:
            query = case_property_query(case_property_name, value, fuzzy=context.fuzzy)
            if op == NEQ:
                query = filters.NOT(query)
            return query
        else:
            try:
                return case_property_range_query(case_property_name, **{RANGE_OP_MAPPING[op]: value})
            except (TypeError, ValueError):
                raise CaseFilterError(
                    _("The right hand side of a comparison must be a number or date. "
                      "Dates must be surrounded in quotation marks"),
                    serialize(node),
                )

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

        if _is_ancestor_case_lookup(node):
            # this node represents a filter on a property for a related case
            return _walk_ancestor_cases(node)

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


def build_filter_from_xpath(domain, xpath, fuzzy=False):
    """Given an xpath expression this function will generate an Elasticsearch
    filter"""
    error_message = _(
        "We didn't understand what you were trying to do with {}. "
        "Please try reformatting your query. "
        "The operators we accept are: {}"
    )

    context = SearchFilterContext(domain, fuzzy)
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
