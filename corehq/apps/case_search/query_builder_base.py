from corehq.apps.case_search.endpoint_query_spec import ParameterInput


class BaseCaseSearchEndpointQueryBuilder:
    """Walks a parsed query-builder AST (GroupNode/ComponentNode) and
    resolves parameter references, deferring backend-specific leaf
    translation and boolean combination to subclasses (e.g. Elasticsearch,
    SQL).
    """
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
        raise NotImplementedError
