from datetime import date

from sqlalchemy import and_, cast, func, literal, not_, or_, select

from corehq import toggles
from corehq.apps.case_search.const import CASE_SEARCH_MAX_RESULTS
from corehq.apps.case_search.endpoint_capability import (
    FIELD_TYPE_DATE,
    FIELD_TYPE_DATETIME,
    FIELD_TYPE_GPS,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_SELECT,
)
from corehq.apps.case_search.query_builder_base import BaseCaseSearchEndpointQueryBuilder
from corehq.apps.case_search.xpath_functions.query_functions import date_permutations
from corehq.apps.es import queries
from corehq.apps.project_db.populate import coerce_to_date, coerce_to_gps, coerce_to_number, coerce_to_select
from corehq.apps.project_db.query import rows_to_cases, to_distance_in_meters
from corehq.apps.project_db.table_ddl import CaseTable, Earth, get_project_db_engine, property_column


class CaseSearchEndpointSqlQueryBuilder(BaseCaseSearchEndpointQueryBuilder):
    def __init__(
        self,
        helper,
        case_type,
        query_root):
        super().__init__(query_root)
        self.request_domain = helper.domain
        self.case_type = case_type
        self.helper = helper
        self.config = helper.config
        self.table = CaseTable(self.request_domain, self.case_type).reflect()

    def build_query(self, search_criteria):
        query = self._get_initial_query()
        where_clause = self._parse_query_root(search_criteria)
        if where_clause is None:
            # Every condition dropped (e.g. all inputs were unsupplied
            # parameters). Apply no extra filter rather than match-all-via-empty.
            return query
        return query.where(where_clause)

    def _get_initial_query(self):
        max_results = CASE_SEARCH_MAX_RESULTS
        if toggles.INCREASED_MAX_SEARCH_RESULTS.enabled(self.request_domain):
            max_results = 1500

        return select(self.table.columns).limit(max_results)

    def _combine_and(self, children):
        return and_(*children)

    def _combine_or(self, children):
        return or_(*children)

    def _combine_none(self, children):
        return not_(and_(*children))

    def _parse_component_node(self, node):
        operator = node.operator
        column = self.table.columns[property_column(node.field, node.field_type)]

        if node.field_type == FIELD_TYPE_GPS:
            if operator == 'within_distance':
                point = coerce_to_gps(self._input_value(node.inputs.get('point')))
                distance = self._input_value(node.inputs.get('distance'))
                unit = self._input_value(node.inputs.get('unit'))
                if None in (point, distance, unit):
                    return None
                if unit not in queries.DISTANCE_UNITS:
                    return None
                try:
                    distance = to_distance_in_meters(distance, unit)
                except ValueError:
                    return None
                earth_point = cast(literal(point), Earth)
                return func.earth_distance(column, earth_point) <= distance
            return None

        value = self._input_value(node.inputs['value'])
        if value is None:
            return None  # ignore component if value is not given

        if node.field_type in (FIELD_TYPE_DATE, FIELD_TYPE_DATETIME):
            date_value = coerce_to_date(value)
            if date_value is None:
                return None
            if operator == 'equals':
                return column == date_value
            elif operator == 'lt':
                return column < date_value
            elif operator == 'gt':
                return column > date_value
            elif operator == 'lte':
                return column <= date_value
            elif operator == 'gte':
                return column >= date_value
            elif operator == 'fuzzy_date':
                return column.in_([date.fromisoformat(p) for p in date_permutations(value)])
            return None
        elif node.field_type == FIELD_TYPE_NUMBER:
            number_value = coerce_to_number(value)
            if number_value is None:
                return None
            if operator == 'equals':
                return column == value
            elif operator == 'not_equals':
                return column != value
            elif operator == 'lt':
                return column < value
            elif operator == 'gt':
                return column > value
            elif operator == 'lte':
                return column <= value
            elif operator == 'gte':
                return column >= value
            return None
        elif node.field_type == FIELD_TYPE_SELECT:
            arr_value = coerce_to_select(value)
            if operator == 'selected_any':
                return column.overlap(arr_value)
            elif operator == 'selected_all':
                return column.contains(arr_value)
            elif operator == 'is_empty':
                return func.cardinality(column) == 0
            return None
        else:
            if operator == 'equals':
                return column == value
            elif operator == 'not_equals':
                return column != value
            elif operator == 'starts_with':
                return column.startswith(value)
            elif operator == 'fuzzy':
                return func.similarity(column, value) >= 0.3
            elif operator == 'phonetic':
                return func.dmetaphone(column) == func.dmetaphone(value)
            return None


def get_sql_endpoint_results(helper, case_type, criteria, endpoint_query, limit=None):
    builder = CaseSearchEndpointSqlQueryBuilder(helper, case_type, endpoint_query)
    with helper.profiler.timing_context('build_query'):
        query = builder.build_query(criteria)
    if limit:
        query = query.limit(limit)

    engine = get_project_db_engine()

    with engine.begin() as conn:
        # In sqlalchemy 1.4+, use execution_options postgresql_readonly
        # conn.execute(sqlalchemy.text('SET TRANSACTION READ ONLY'))
        # DomainSchema(domain).set_local_search_path(conn)
        result = conn.execute(query)
        rows = result.fetchall()
        cases = rows_to_cases(rows, builder.table, builder.request_domain, case_type)
    return cases
