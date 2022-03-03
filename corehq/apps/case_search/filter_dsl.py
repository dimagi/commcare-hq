import re
from collections import Counter
from dataclasses import dataclass

from django.utils.translation import ugettext as _

from eulxml.xpath import parse as parse_xpath
from eulxml.xpath.ast import FunctionCall, Step, UnaryExpression, BinaryExpression, serialize

from corehq.apps.case_search.xpath_functions import (
    XPATH_VALUE_FUNCTIONS,
    XPathFunctionException,
)
from corehq.apps.es import filters, queries
from corehq.apps.es.case_search import (
    CaseSearchES,
    case_property_query,
    case_property_range_query,
    reverse_index_case_query,
)


class CaseFilterError(Exception):

    def __init__(self, message, filter_part):
        self.filter_part = filter_part
        super(CaseFilterError, self).__init__(message)


class TooManyRelatedCasesError(CaseFilterError):
    pass


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


def build_filter_from_ast(domain, node, fuzzy=False):
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
        if isinstance(node.right, Step):
            _raise_step_RHS(node)
        new_query = '{} {} "{}"'.format(serialize(node.left.right), node.op, node.right)

        es_query = CaseSearchES().domain(domain).xpath_query(domain, new_query, fuzzy=fuzzy)
        if es_query.count() > MAX_RELATED_CASES:
            raise TooManyRelatedCasesError(
                _("The related case lookup you are trying to perform would return too many cases"),
                new_query
            )

        return es_query.scroll_ids()

    def _child_case_lookup(case_ids, identifier):
        """returns a list of all case_ids who have parents `case_id` with the relationship `identifier`
        """
        return CaseSearchES().domain(domain).get_child_cases(case_ids, identifier).scroll_ids()

    def _is_ancestor_case_lookup(node):
        """Returns whether a particular AST node is an ancestory case lookup

        e.g. `parent/host/thing = 'foo'`
        """
        return hasattr(node, 'left') and hasattr(node.left, 'op') and node.left.op == '/'

    def _subcase_filter(node):
        index_identifier, subcase_predicate, count_op, case_count, invert_condition = _parse_normalize_subcase_query(node)
        ids = _get_parent_case_ids_matching_subcase_query(index_identifier, subcase_predicate, count_op, case_count)
        if invert_condition:
            return filters.NOT(filters.doc_id(ids))
        return filters.doc_id(ids)

    def _get_parent_case_ids_matching_subcase_query(index_identifier, subcase_predicates, count_op, case_count):
        """Get a list of case IDs for cases that have a subcase with the given index identifier
        and matching the subcase predicate filter.

        Only cases with `> case_count_gt` subcases will be returned.
        """
        # TODO: validate that the subcase filter doesn't contain any ancestor filtering
        subcase_filter = build_filter_from_ast(domain, subcase_predicates, fuzzy=fuzzy)

        index_query = queries.nested(
            'indices',
            queries.filtered(
                queries.match_all(),
                filters.AND(
                    filters.term('indices.identifier', index_identifier),
                    filters.NOT(filters.term('indices.referenced_id', ''))  # exclude deleted indices
                )
            )
        )
        subcase_query = (
            CaseSearchES().domain(domain)
                .filter(index_query)
                .filter(subcase_filter)
                .source('indices')
        )

        if subcase_query.count() > MAX_RELATED_CASES:
            raise TooManyRelatedCasesError(
                _("The related case lookup you are trying to perform would return too many cases"),
                ' and '.join([serialize(predicate) for predicate in subcase_predicates])
            )

        parent_case_id_counter = Counter()
        for subcase in subcase_query.run().hits:
            indices = [index for index in subcase['indices'] if index['identifier'] == index_identifier]
            if indices:
                parent_case_id_counter.update([indices[0]['referenced_id']])

        # TODO: support '=' as well as '>' for the comparison operator: 'count_op'
        if case_count <= 0:
            return list(parent_case_id_counter)

        return [
            case_id for case_id, count in parent_case_id_counter.items() if count > case_count
        ]

    def _is_subcase_lookup(node):
        """Returns whether a particular AST node is a subcase lookup."""
        return False  # TODO

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
            return XPATH_VALUE_FUNCTIONS[node.name](node)
        except KeyError:
            raise CaseFilterError(
                _("We don't know what to do with the function \"{}\". Accepted functions are: {}").format(
                    node.name,
                    ", ".join(list(XPATH_VALUE_FUNCTIONS.keys())),
                ),
                serialize(node)
            )
        except XPathFunctionException as e:
            raise CaseFilterError(str(e), serialize(node))

    def _equality(node):
        """Returns the filter for an equality operation (=, !=)

        """
        acceptable_rhs_types = (int, str, float, FunctionCall, UnaryExpression)
        if isinstance(node.left, Step) and (
                isinstance(node.right, acceptable_rhs_types)):
            # This is a leaf node
            case_property_name = serialize(node.left)
            value = _unwrap_function(node.right)
            q = case_property_query(case_property_name, value, fuzzy=fuzzy)

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
            # TODO: adjust this for subcase queries
            raise CaseFilterError(
                _("Your search query is required to have at least one boolean operator ({boolean_ops})").format(
                    boolean_ops=", ".join(list(COMPARISON_MAPPING.keys()) + [EQ, NEQ]),
                ),
                serialize(node)
            )

        if _is_ancestor_case_lookup(node):
            # this node represents a filter on a property for a related case
            return _walk_ancestor_cases(node)

        if _is_subcase_lookup(node):
            return _subcase_filter(node)

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


@dataclass
class SubCaseQuery:
    index_identifier: str
    subcase_filter: object
    count_op: str
    count: int
    invert: bool

    def as_tuple(self):
        return (
            self.index_identifier, serialize(self.subcase_filter), self.count_op, self.count, self.invert
        )


def _parse_normalize_subcase_query(node):
    """Parse the subcase query and normalize it to the form 'subcase_count > N' or 'subcase_count = N'

    Supports the following syntax:
    - subcase_exists[identifier='X'][ {subcase filter} ]
    - subcase_count[identifier='X'][ {subcase_filter} ] {one of =, !=, >, <, >=, <= } {integer value}
    - not( subcase query )

    :returns: tuple(index_identifier, subcase search predicates, count_op, case_count, invert_condition)
    - index_identifier: the name of the index identifier to match on
    - subcase search predicates: list of predicates used to filter the subcase query
    - count_op: One of ['>', '=']
    - case_count: Integer value used in conjunction with count_op to filter parent cases
    - invert_condition: True if the initial expression is one of ['<', '<=']
    """
    def parse_predicates(node):
        if node.op in ['and', 'or']:
            return [node.left, node.right]
        return [node]

    # NOTES:
    #  - instead of returning a tuple we could create a dataclass to make it easier to work with and
    #    could encapsulate some functionality:
    #       subcase_query.include_parent(subcase_count)
    #       subcase_query.create_parent_filter(matching_parent_ids)

    current_node = node
    invert_condition = False

    try:
        assert isinstance(current_node, (FunctionCall, BinaryExpression, Step))
    except AssertionError:
        raise TypeError("Xpath incorrectly formatted. Check your subcase function syntax.")

    # If xpath is a NOT(query), set invert_condition and get first arg
    if isinstance(current_node, FunctionCall):
        if current_node.name.lower() == "not":
            invert_condition = not invert_condition
            current_node = current_node.args[0]

    # If subcase query is a count comparison:
    # Set current_op and case_count, and traverse to left node
    if isinstance(current_node, BinaryExpression):
        count_op = current_node.op
        case_count = current_node.right
        current_node = current_node.left

    print(current_node)
    try:
        assert str(current_node.name) in ["subcase_exists", "subcase_count"]
    except AssertionError:
        raise ValueError(
            "Xpath incorrectly formatted."
            f"Expected: subcase_exists or subcase_count. Received: {current_node.name}"
        )

    if str(current_node.name) == "subcase_exists":
        case_count = 0
        count_op = ">"

    try:
        assert count_op in [">", "<", "<=", ">=", "=", "!="]
    except AssertionError:
        raise TypeError(f"Xpath incorrectly formatted. Check comparison operator. Received: {count_op}")

    if count_op in ["<", "<="]:
        invert_condition = not invert_condition

    if count_op in [">=", "<"]:
        case_count -= 1

    if count_op == "!=":
        count_op = '='
        invert_condition = not invert_condition

    if count_op != "=":
        count_op = ">"

    if count_op == "=" and case_count == 0:
        count_op = ">"
        invert_condition = not invert_condition

    index_indetifier = current_node.args[0]
    # subcase_predicates = parse_predicates(current_node.args[1])
    subcase_predicates = current_node.args[1]

    print(index_indetifier, subcase_predicates, count_op, case_count, invert_condition)

    return SubCaseQuery(index_indetifier, subcase_predicates, count_op, case_count, invert_condition)


def build_filter_from_xpath(domain, xpath, fuzzy=False):
    error_message = _(
        "We didn't understand what you were trying to do with {}. "
        "Please try reformatting your query. "
        "The operators we accept are: {}"
    )
    try:
        return build_filter_from_ast(domain, parse_xpath(xpath), fuzzy=fuzzy)
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
