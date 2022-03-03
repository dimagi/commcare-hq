from collections import Counter
from dataclasses import dataclass

from django.utils.translation import ugettext as _

from eulxml.xpath.ast import BinaryExpression, FunctionCall, Step, serialize

from corehq.apps.es import CaseSearchES, filters, queries


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


def subcase(domain, node, fuzzy=False):
    subcase_query = _parse_normalize_subcase_query(node)
    ids = _get_parent_case_ids_matching_subcase_query(domain, subcase_query, fuzzy)
    if subcase_query.invert:
        return filters.NOT(filters.doc_id(ids))
    return filters.doc_id(ids)


def _get_parent_case_ids_matching_subcase_query(domain, subcase_query, fuzzy=False):
    """Get a list of case IDs for cases that have a subcase with the given index identifier
    and matching the subcase predicate filter.

    Only cases with `> case_count_gt` subcases will be returned.
    """
    # TODO: validate that the subcase filter doesn't contain any ancestor filtering
    from corehq.apps.case_search.filter_dsl import (
        MAX_RELATED_CASES,
        TooManyRelatedCasesError,
        build_filter_from_ast,
    )

    subcase_filter = build_filter_from_ast(domain, subcase_query.subcase_filter, fuzzy=fuzzy)

    index_query = queries.nested(
        'indices',
        queries.filtered(
            queries.match_all(),
            filters.AND(
                filters.term('indices.identifier', subcase_query.index_identifier),
                filters.NOT(filters.term('indices.referenced_id', ''))  # exclude deleted indices
            )
        )
    )
    es_query = (
        CaseSearchES().domain(domain)
        .filter(index_query)
        .filter(subcase_filter)
        .source('indices')
    )

    if es_query.count() > MAX_RELATED_CASES:
        raise TooManyRelatedCasesError(
            _("The related case lookup you are trying to perform would return too many cases"),
            serialize(subcase_query.subcase_filter)
        )

    parent_case_id_counter = Counter()
    for subcase in es_query.run().hits:
        indices = [index for index in subcase['indices'] if index['identifier'] == subcase_query.index_identifier]
        if indices:
            parent_case_id_counter.update([indices[0]['referenced_id']])

    # TODO: support '=' as well as '>' for the comparison operator: 'count_op'
    if subcase_query.count <= 0:
        return list(parent_case_id_counter)

    return [
        case_id for case_id, count in parent_case_id_counter.items() if count > subcase_query.count
    ]


def _parse_normalize_subcase_query(node):
    """Parse the subcase query and normalize it to the form 'subcase-count > N' or 'subcase-count = N'

    Supports the following syntax:
    - subcase-exists[identifier='X'][ {subcase filter} ]
    - subcase-count[identifier='X'][ {subcase_filter} ] {one of =, !=, >, <, >=, <= } {integer value}
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
    #       subcase_query.include_parent(subcase-count)
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
        assert str(current_node.name) in ["subcase-exists", "subcase-count"]
    except AssertionError:
        raise ValueError(
            "Xpath incorrectly formatted."
            f"Expected: subcase-exists or subcase-count. Received: {current_node.name}"
        )

    if str(current_node.name) == "subcase-exists":
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
    subcase_predicates = current_node.args[1]

    return SubCaseQuery(index_indetifier, subcase_predicates, count_op, case_count, invert_condition)
