from django.utils.translation import gettext
from eulxml.xpath import serialize

from corehq.apps.case_search.exceptions import TooManyRelatedCasesError
from corehq.apps.case_search.filter_dsl import MAX_RELATED_CASES
from corehq.apps.case_search.xpath_functions.comparison import property_comparison_query
from corehq.apps.es.case_search import CaseSearchES, reverse_index_case_query


def is_ancestor_path_expression(node):
    """Returns whether a particular AST node is an ancestor path expression

    e.g.
     - `parent/host/thing`
     - `parent/host/thing = 'foo'`
    """
    return hasattr(node, 'left') and hasattr(node.left, 'op') and node.left.op == '/'


def ancestor_comparison_query(context, node):
    """Return a query that will fulfill the filter on the related case.

    :param node: a node returned from eulxml.xpath.parse of the form `parent/grandparent/property = 'value'`

    Since ES has no way of performing joins, we filter down in stages:
    1. Find the ids of all cases where the condition is met
    2. Walk down the case hierarchy, finding all related cases with the right identifier to the ids
    found in (1).
    3. Return the lowest of these ids as a related case query filter
    """

    # fetch the ids of the highest level cases that match the case_property
    # i.e. all the cases which have `property = 'value'`
    case_ids = _parent_property_lookup(context, node)

    return walk_ancestor_hierarchy(context, node.left, case_ids)


def walk_ancestor_hierarchy(context, node, case_ids):
    """Given a set of case IDs and an ancestor path expression this function
    will walk down the case hierarchy, finding all cases related to 'case_ids' using the
    relationship identifier from the ancestor path expression.

    :param node: a node returned from eulxml.xpath.parse of the form `parent/grandparent/property = 'value'`
    :returns: Return the lowest of these ids as a related case query filter
    """

    # get the related case path we need to walk, i.e. `parent/grandparent/property`
    while is_ancestor_path_expression(node):
        # This walks down the tree and finds case ids that match each identifier
        # This is basically performing multiple "joins" to find related cases since ES
        # doesn't have a way to relate models together

        # Get the path to the related case, e.g. `parent/grandparent`
        # On subsequent run throughs, it walks down the tree (e.g. n = [parent, /, grandparent])
        node = node.left
        identifier = serialize(node.right)  # the identifier at this step, e.g. `grandparent`

        # get the ids of the cases that point at the previous level's cases
        # this has the potential of being a very large list
        case_ids = _child_case_lookup(context, case_ids, identifier=identifier)
        if not case_ids:
            break

    # after walking the full tree, get the final level we are interested in, i.e. `parent`
    final_identifier = serialize(node.left)
    return reverse_index_case_query(case_ids, final_identifier)


def _parent_property_lookup(context, node):
    """given a node of the form `parent/foo = 'thing'`, return all case_ids where `foo = thing`
    """
    es_filter = property_comparison_query(node.left.right, node.op, node.right, node)
    es_query = CaseSearchES().domain(context.domain).filter(es_filter)
    if es_query.count() > MAX_RELATED_CASES:
        new_query = '{} {} "{}"'.format(serialize(node.left.right), node.op, node.right)
        raise TooManyRelatedCasesError(
            gettext("The related case lookup you are trying to perform would return too many cases"),
            new_query
        )

    return es_query.scroll_ids()


def _child_case_lookup(context, case_ids, identifier):
    """returns a list of all case_ids who have parents `case_id` with the relationship `identifier`
    """
    return CaseSearchES().domain(context.domain).get_child_cases(case_ids, identifier).scroll_ids()
