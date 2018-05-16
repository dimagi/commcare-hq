from __future__ import absolute_import, print_function, unicode_literals

from django.utils.translation import ugettext as _
from eulxml.xpath.ast import Step, serialize
from six import integer_types, string_types

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


def build_filter_from_ast(domain, node):
    """Builds an ES filter from an AST provided by eulxml.xpath.parse
    """

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
        return CaseSearchES().domain(domain).xpath_query(domain, new_query).scroll_ids()

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
              "quotation marks.").format(serialize(node.right)),
            serialize(node)
        )

    def _equality(node):
        """Returns the filter for an equality operation (=, !=)

        """
        if isinstance(node.left, Step) and isinstance(node.right, integer_types + (string_types, float)):
            # This is a leaf node
            case_property_name = serialize(node.left)
            value = node.right

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
            value = node.right
            return case_property_range_query(case_property_name, **{COMPARISON_MAPPING[node.op]: value})
        except TypeError:
            raise CaseFilterError(
                _("The right hand side of a comparison must be a number or date"),
                serialize(node),
            )


    def visit(node):
        if not hasattr(node, 'op'):
            raise CaseFilterError(
                _("Your filter is required to have at least one boolean operator (e.g. '=', '!=')"),
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
