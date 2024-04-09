from collections import Counter
from dataclasses import dataclass

from django.utils.translation import gettext as _
from eulxml.xpath.ast import (
    BinaryExpression,
    FunctionCall,
    UnaryExpression,
    serialize,
)

from corehq.apps.case_search.const import MAX_RELATED_CASES
from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.es import CaseSearchES, filters, queries


@dataclass
class SubCaseQuery:
    index_identifier: str
    """The name of the index identifier to match on"""

    subcase_filter: object
    """AST class representing the subcase filter expression"""

    op: str
    """One of ['>', '=']"""

    count: int
    """Integer value used in conjunction with op to filter parent cases"""

    invert: bool
    """True if the initial expression is one of ['<', '<=']"""

    def __post_init__(self):
        ops = ('>', '=')
        if self.op not in ops:
            raise ValueError(f"op must be one of {ops}")

    def as_tuple(self):
        subcase_filter = serialize(self.subcase_filter) if self.subcase_filter else None
        return (
            self.index_identifier, subcase_filter, self.op, self.count, self.invert
        )

    def filter_count(self, count):
        if self.op == '>':
            return count > self.count
        return self.count == count


def subcase(node, context):
    """
    Supports the following syntax:
    - subcase-exists('parent', {subcase filter} )
    - subcase-count('host', {subcase_filter} ) {=, !=, >, <, >=, <=} {integer value}
    """
    subcase_query = _parse_normalize_subcase_query(node)
    ids = _get_parent_case_ids_matching_subcase_query(subcase_query, context)
    if subcase_query.invert:
        if not ids:
            return filters.match_all()
        return filters.NOT(filters.doc_id(ids))
    # uncomment once we are on ES > 2.4
    # if not ids:
    #     return filters.match_none()
    return filters.doc_id(ids)


def _get_parent_case_ids_matching_subcase_query(subcase_query, context):
    """Get a list of case IDs for cases that have a subcase with the given index identifier
    and matching the subcase predicate filter.

    Only cases with `[>,=] case_count_gt` subcases will be returned.
    """

    counts_by_parent_id = Counter(
        index['referenced_id']
        for subcase in _run_subcase_query(subcase_query, context)
        for index in subcase['indices']
        if index['identifier'] == subcase_query.index_identifier
    )
    if len(counts_by_parent_id) > MAX_RELATED_CASES:
        from ..exceptions import TooManyRelatedCasesError
        raise TooManyRelatedCasesError(
            _("The related case lookup you are trying to perform would return too many cases"),
            serialize(subcase_query.subcase_filter)
        )

    if subcase_query.op == '>' and subcase_query.count <= 0:
        return list(counts_by_parent_id)

    return [
        case_id for case_id, count in counts_by_parent_id.items() if subcase_query.filter_count(count)
    ]


def _run_subcase_query(subcase_query, context):
    from corehq.apps.case_search.filter_dsl import (
        build_filter_from_ast,
    )

    if subcase_query.subcase_filter:
        subcase_filter = build_filter_from_ast(subcase_query.subcase_filter, context)
    else:
        subcase_filter = filters.match_all()

    es_query = (
        CaseSearchES().domain(context.domain)
        .nested(
            'indices',
            filters.term('indices.identifier', subcase_query.index_identifier),
            filters.NOT(filters.term('indices.referenced_id', ''))  # exclude deleted indices
        )
        .filter(subcase_filter)
        .source(['indices.referenced_id', 'indices.identifier'])
    )

    context.profiler.add_query('subcase_query', es_query)
    with context.profiler.timing_context('subcase_query'):
        return es_query.run().hits


def _parse_normalize_subcase_query(node) -> SubCaseQuery:
    """Parse the subcase query and normalize it to the form 'subcase-count > N' or 'subcase-count = N'
    """
    index_identifier, subcase_filter, count_op, case_count = _extract_subcase_query_parts(node)
    case_count, count_op, invert_condition = _normalize_param(case_count, count_op)
    return SubCaseQuery(index_identifier, subcase_filter, count_op, case_count, invert_condition)


def _normalize_param(case_count, count_op):
    invert_condition = False
    if count_op == "<":
        # count < N -> not( count > N - 1 )
        count_op = ">"
        invert_condition = not invert_condition
        case_count -= 1
    elif count_op == "<=":
        # count <= N -> not( count > N )
        count_op = ">"
        invert_condition = not invert_condition
    elif count_op == ">=":
        # count >= N -> count > N -1
        count_op = ">"
        case_count -= 1
    elif count_op == "!=":
        # count != N -> not( count = N )
        count_op = '='
        invert_condition = not invert_condition
    if count_op == "=" and case_count == 0:
        # count = 0 -> not( count > 0 )
        count_op = ">"
        invert_condition = not invert_condition
    return case_count, count_op, invert_condition


def _extract_subcase_query_parts(node):
    current_node = node
    if isinstance(node, BinaryExpression):
        count_op = node.op
        case_count = node.right
        current_node = node.left

        if count_op not in [">", "<", "<=", ">=", "=", "!="]:
            raise XPathFunctionException(
                _("Unsupported operator for use with 'subcase-count': {op}").format(op=count_op),
                serialize(node)
            )

        if isinstance(case_count, UnaryExpression):
            if case_count.op == '+':
                case_count = case_count.right
            else:
                raise XPathFunctionException(
                    _("'subcase-count' must be compared to a positive integer"),
                    serialize(node)
                )

        try:
            case_count = int(case_count)
        except (ValueError, TypeError):
            raise XPathFunctionException(
                _("'subcase-count' must be compared to a positive integer"),
                serialize(node)
            )

        if not isinstance(current_node, FunctionCall) or str(current_node.name) != "subcase-count":
            raise XPathFunctionException(
                _("XPath incorrectly formatted. Expected 'subcase-count'"),
                serialize(current_node)
            )

    else:
        if not isinstance(node, FunctionCall) or str(node.name) != "subcase-exists":
            raise XPathFunctionException(
                _("XPath incorrectly formatted. Expected 'subcase-exists'"),
                serialize(node)
            )

        case_count = 0
        count_op = ">"

    args = current_node.args
    if not 1 <= len(args) <= 2:
        raise XPathFunctionException(
            _("'{name}' expects one or two arguments").format(name=current_node.name),
            serialize(node)
        )
    index_identifier = args[0]
    subcase_filter = args[1] if len(args) == 2 else None

    if not isinstance(index_identifier, str):
        raise XPathFunctionException(
            _("'{name}' error. Index identifier must be a string").format(name=current_node.name),
            serialize(node)
        )

    return index_identifier, subcase_filter, count_op, case_count
