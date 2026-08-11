from corehq import toggles
from corehq.apps.case_search.const import CASE_SEARCH_MAX_RESULTS
from corehq.apps.case_search.endpoint_capability import (
    _OPERATOR_BY_TYPE,
    FIELD_TYPE_DATE,
    FIELD_TYPE_DATETIME,
    FIELD_TYPE_GPS,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_SELECT,
    FIELD_TYPE_TEXT,
)
from corehq.apps.case_search.endpoint_query_spec import ParameterInput


def build_operator_handlers(field_type_methods):
    """Build a {(field_type, operator): method_name} dispatch table from the
    declared _OPERATOR_BY_TYPE capability data, routing every declared
    operator to its field type's handler method.
    """
    return {
        (field_type, operator): field_type_methods[field_type]
        for field_type, operators in _OPERATOR_BY_TYPE.items()
        for operator, _label in operators
    }


def resolve_max_results(domain):
    if toggles.INCREASED_MAX_SEARCH_RESULTS.enabled(domain):
        return 1500
    return CASE_SEARCH_MAX_RESULTS


class BaseCaseSearchEndpointQueryBuilder:
    """Walks a parsed query-builder AST (GroupNode/ComponentNode) and
    resolves parameter references, deferring backend-specific leaf
    translation and boolean combination to subclasses (e.g. Elasticsearch,
    SQL).

    Subclasses must implement _parse_gps/_parse_date/_parse_number/
    _parse_select/_parse_text, each taking (node, operator).
    """
    _FIELD_TYPE_METHODS = {
        FIELD_TYPE_GPS: '_parse_gps',
        FIELD_TYPE_DATE: '_parse_date',
        FIELD_TYPE_DATETIME: '_parse_date',
        FIELD_TYPE_NUMBER: '_parse_number',
        FIELD_TYPE_SELECT: '_parse_select',
        FIELD_TYPE_TEXT: '_parse_text',
    }
    OPERATOR_HANDLERS = build_operator_handlers(_FIELD_TYPE_METHODS)

    def __init__(self, query_root):
        self.query_root = query_root

    def _parse_query_root(self, search_criteria):
        self.param_values = {c.key: c.value for c in search_criteria}
        return self._parse_query(self.query_root)

    def _get_child_queries(self, node):
        child_queries = [self._parse_query(child) for child in node.children]
        return [q for q in child_queries if q is not None]

    def _parse_query(self, node):
        if node.type in ('all', 'any', 'none'):
            # Drop a group with no surviving children rather than collapsing to
            # an empty AND/OR. An empty bool matches all documents, which in an
            # `any`/OR context would make the whole query match everything.
            children = self._get_child_queries(node)
            if not children:
                return None
            if node.type == 'all':
                return self._combine_and(children)
            if node.type == 'any':
                return self._combine_or(children)
            return self._combine_none(children)
        elif node.type == 'component':
            return self._parse_component_node(node)
        else:
            return None

    def _input_value(self, input_):
        if input_ is None:
            return None
        if isinstance(input_, ParameterInput):
            return self.param_values.get(input_.value)
        return input_.value

    def _combine_and(self, children):
        raise NotImplementedError

    def _combine_or(self, children):
        raise NotImplementedError

    def _combine_none(self, children):
        raise NotImplementedError

    def _parse_component_node(self, node):
        handler_name = self.OPERATOR_HANDLERS.get((node.field_type, node.operator))
        if handler_name is None:
            return None
        return getattr(self, handler_name)(node, node.operator)
