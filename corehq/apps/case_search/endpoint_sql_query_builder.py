from datetime import date

from django.utils.translation import gettext as _
from sqlalchemy import and_, cast, func, literal, not_, or_, select

from corehq.apps.case_search.const import DISTANCE_UNITS, DISTANCE_UNITS_TO_METER
from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.query_builder_base import (
    BaseCaseSearchEndpointQueryBuilder,
    resolve_max_results,
)
from corehq.apps.case_search.xpath_functions.query_functions import (
    date_permutations,
)
from corehq.apps.project_db.populate import (
    coerce_to_date,
    coerce_to_gps,
    coerce_to_number,
    coerce_to_select,
)
from corehq.apps.project_db.query import rows_to_cases
from corehq.apps.project_db.table_ddl import (
    CaseTable,
    Earth,
    get_project_db_engine,
    property_column,
)


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
        if self.table is None:
            raise CaseSearchUserError(
                _("No search table found for case type '{case_type}' in domain '{domain}'").format(
                    case_type=self.case_type, domain=self.request_domain
                )
            )

    def build_query(self, search_criteria):
        query = self._get_initial_query()
        where_clause = self._parse_query_root(search_criteria)
        if where_clause is None:
            # Every condition dropped (e.g. all inputs were unsupplied
            # parameters). Apply no extra filter rather than match-all-via-empty.
            return query
        return query.where(where_clause)

    def _get_initial_query(self):
        max_results = resolve_max_results(self.request_domain)
        return select(self.table.columns).limit(max_results)

    def _combine_and(self, children):
        return and_(*children)

    def _combine_or(self, children):
        return or_(*children)

    def _combine_none(self, children):
        return not_(and_(*children))

    def _column(self, node):
        return self.table.columns[property_column(node.field, node.field_type)]

    def _parse_gps(self, node, operator):
        if operator != 'within_distance':
            return None
        column = self._column(node)
        point = coerce_to_gps(self._input_value(node.inputs.get('point')))
        distance = self._input_value(node.inputs.get('distance'))
        unit = self._input_value(node.inputs.get('unit'))
        if None in (point, distance, unit):
            return None
        if unit not in DISTANCE_UNITS:
            return None
        try:
            distance = float(distance) * DISTANCE_UNITS_TO_METER.get(unit, 1)
        except ValueError:
            return None
        earth_point = cast(literal(point), Earth)
        return func.earth_distance(column, earth_point) <= distance

    def _parse_date(self, node, operator):
        column = self._column(node)
        value = self._input_value(node.inputs['value'])
        if value is None:
            return None  # ignore component if value is not given
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

    def _parse_number(self, node, operator):
        column = self._column(node)
        value = self._input_value(node.inputs['value'])
        if value is None:
            return None  # ignore component if value is not given
        number_value = coerce_to_number(value)
        if number_value is None:
            return None
        if operator == 'equals':
            return column == number_value
        elif operator == 'not_equals':
            return column != number_value
        elif operator == 'lt':
            return column < number_value
        elif operator == 'gt':
            return column > number_value
        elif operator == 'lte':
            return column <= number_value
        elif operator == 'gte':
            return column >= number_value
        return None

    def _parse_select(self, node, operator):
        column = self._column(node)
        value = self._input_value(node.inputs['value'])
        if value is None:
            return None  # ignore component if value is not given
        arr_value = coerce_to_select(value)
        if operator == 'selected_any':
            return column.overlap(arr_value)
        elif operator == 'selected_all':
            return column.contains(arr_value)
        elif operator == 'is_empty':
            return func.cardinality(column) == 0
        return None

    def _parse_text(self, node, operator):
        column = self._column(node)
        value = self._input_value(node.inputs['value'])
        if value is None:
            return None  # ignore component if value is not given
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
