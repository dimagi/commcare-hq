from django.utils.translation import gettext
from eulxml.xpath import serialize
from eulxml.xpath.ast import Step
import json

from corehq.apps.case_search.dsl_utils import unwrap_value
from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.case_search.const import RANGE_OP_MAPPING, EQ, NEQ
from corehq.apps.es import filters
from corehq.apps.es.case_search import case_property_query, case_property_range_query


def property_comparison_query(context, case_property_name_raw, op, value_raw, node):
    if not isinstance(case_property_name_raw, Step):
        raise CaseFilterError(
            gettext("We didn't understand what you were trying to do with {}").format(serialize(node)),
            serialize(node)
        )

    case_property_name = serialize(case_property_name_raw)
    value = unwrap_value(value_raw, context)

    # In initial xpath parsing, multiple terms are converted to string
    # i.e "['val1','val2']". This converts it back to a list for ES to filter by
    if context.multi_term:
        value = _parse_multiple_terms_list_str(value)

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
                gettext("The right hand side of a comparison must be a number or date. "
                  "Dates must be surrounded in quotation marks"),
                serialize(node),
            )


def _parse_multiple_terms_list_str(value):
    # Given a string representation of a list of strings, returns a list.
    value = value.replace("'", '"')  # '["abc123", "def456"]'
    return json.loads(value)
