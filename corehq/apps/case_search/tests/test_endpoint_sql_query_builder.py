import datetime
import uuid

import pytest

from sqlalchemy import Column, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY
from unmagic import use

from corehq.apps.case_search.endpoint_capability import (
    _OPERATOR_BY_TYPE,
    FIELD_TYPE_DATE,
    FIELD_TYPE_DATETIME,
    FIELD_TYPE_GPS,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_SELECT,
    FIELD_TYPE_TEXT,
)
from corehq.apps.case_search.endpoint_query_spec import (
    ComponentNode,
    ConstantInput,
    GroupNode,
    ParameterInput,
)
from corehq.apps.case_search.endpoint_sql_query_builder import CaseSearchEndpointSqlQueryBuilder
from corehq.apps.es.queries import DISTANCE_UNITS
from corehq.apps.project_db.populate import send_to_project_db
from corehq.apps.project_db.table_ddl import get_project_db_engine, property_column
from corehq.apps.project_db.tests.util import project_db_table
from corehq.form_processor.models import CommCareCase


def _make_builder(field='some_field', field_type=FIELD_TYPE_TEXT):
    builder = CaseSearchEndpointSqlQueryBuilder.__new__(CaseSearchEndpointSqlQueryBuilder)
    builder.param_values = {}
    col_type = ARRAY(Text) if field_type == FIELD_TYPE_SELECT else Text
    builder.table = Table(
        'some_case_type', MetaData(),
        Column(property_column(field, field_type), col_type),
    )
    return builder


def _make_geopoint_node(point='12.5 13.5', distance='10', unit='kilometers'):
    inputs = {}
    if point is not None:
        inputs['point'] = ConstantInput(value=point)
    if distance is not None:
        inputs['distance'] = ConstantInput(value=distance)
    if unit is not None:
        inputs['unit'] = ConstantInput(value=unit)
    return ComponentNode(
        operator='within_distance',
        field='gps_field',
        field_type=FIELD_TYPE_GPS,
        inputs=inputs,
    )


def test_parse_component_node_gps_within_distance():
    node = _make_geopoint_node()
    result = _make_builder('gps_field', FIELD_TYPE_GPS)._parse_component_node(node)
    assert result is not None


@pytest.mark.parametrize('missing_input', ['point', 'distance', 'unit'])
def test_parse_component_node_gps_missing_input_returns_none(missing_input):
    kwargs = {missing_input: None}
    node = _make_geopoint_node(**kwargs)
    result = _make_builder('gps_field', FIELD_TYPE_GPS)._parse_component_node(node)
    assert result is None


@pytest.mark.parametrize('bad_point,bad_distance,bad_unit', [
    ('not-a-coordinate', '10', 'kilometers'),
    ('12.5 13.5', 'not-a-number', 'kilometers'),
    ('12.5 13.5', '10', 'parsecs'),
])
def test_parse_component_node_gps_invalid_values_return_none(bad_point, bad_distance, bad_unit):
    node = _make_geopoint_node(point=bad_point, distance=bad_distance, unit=bad_unit)
    result = _make_builder('gps_field', FIELD_TYPE_GPS)._parse_component_node(node)
    assert result is None


def test_parse_component_node_gps_parameter_input():
    node = ComponentNode(
        operator='within_distance',
        field='gps_field',
        field_type=FIELD_TYPE_GPS,
        inputs={
            'point': ParameterInput(value='my_point'),
            'distance': ConstantInput(value='5'),
            'unit': ConstantInput(value='miles'),
        },
    )
    builder = _make_builder('gps_field', FIELD_TYPE_GPS)
    builder.param_values = {'my_point': '10.0 20.0'}
    result = builder._parse_component_node(node)
    assert result is not None


def test_parse_component_node_gps_missing_parameter_value_returns_none():
    node = ComponentNode(
        operator='within_distance',
        field='gps_field',
        field_type=FIELD_TYPE_GPS,
        inputs={
            'point': ParameterInput(value='my_point'),
            'distance': ConstantInput(value='5'),
            'unit': ConstantInput(value='miles'),
        },
    )
    builder = _make_builder('gps_field', FIELD_TYPE_GPS)
    builder.param_values = {}  # parameter not supplied
    result = builder._parse_component_node(node)
    assert result is None


def _make_text_node(operator, value='alice'):
    return ComponentNode(
        operator=operator,
        field='name',
        field_type=FIELD_TYPE_TEXT,
        inputs={'value': ConstantInput(value=value)},
    )


@pytest.mark.parametrize('operator', ['equals', 'not_equals', 'starts_with', 'fuzzy', 'phonetic'])
def test_parse_component_node_text_operators(operator):
    node = _make_text_node(operator)
    result = _make_builder('name', FIELD_TYPE_TEXT)._parse_component_node(node)
    assert result is not None


@pytest.mark.parametrize('operator', ['equals', 'fuzzy', 'phonetic'])
def test_parse_component_node_text_missing_parameter_value_returns_none(operator):
    node = ComponentNode(
        operator=operator,
        field='name',
        field_type=FIELD_TYPE_TEXT,
        inputs={'value': ParameterInput(value='search_term')},
    )
    builder = _make_builder('name', FIELD_TYPE_TEXT)
    builder.param_values = {}  # parameter not supplied
    result = builder._parse_component_node(node)
    assert result is None


def _make_date_node(operator, value='2020-01-01', field_type=FIELD_TYPE_DATE):
    return ComponentNode(
        operator=operator,
        field='dob',
        field_type=field_type,
        inputs={'value': ConstantInput(value=value)},
    )


@pytest.mark.parametrize('operator', ['equals', 'lt', 'gt', 'lte', 'gte', 'fuzzy_date'])
def test_parse_component_node_date_operators(operator):
    node = _make_date_node(operator)
    result = _make_builder('dob', FIELD_TYPE_DATE)._parse_component_node(node)
    assert result is not None


def test_parse_component_node_date_invalid_returns_none():
    node = _make_date_node('equals', value='not-a-date')
    result = _make_builder('dob', FIELD_TYPE_DATE)._parse_component_node(node)
    assert result is None


def _make_number_node(operator, value='5'):
    return ComponentNode(
        operator=operator,
        field='age',
        field_type=FIELD_TYPE_NUMBER,
        inputs={'value': ConstantInput(value=value)},
    )


@pytest.mark.parametrize('operator', ['equals', 'not_equals', 'lt', 'gt', 'lte', 'gte'])
def test_parse_component_node_number_operators(operator):
    node = _make_number_node(operator)
    result = _make_builder('age', FIELD_TYPE_NUMBER)._parse_component_node(node)
    assert result is not None


def test_parse_component_node_number_invalid_returns_none():
    node = _make_number_node('equals', value='not-a-number')
    result = _make_builder('age', FIELD_TYPE_NUMBER)._parse_component_node(node)
    assert result is None


def _make_select_node(operator, value='a'):
    return ComponentNode(
        operator=operator,
        field='color',
        field_type=FIELD_TYPE_SELECT,
        inputs={'value': ConstantInput(value=value)},
    )


@pytest.mark.parametrize('operator', ['selected_any', 'selected_all', 'is_empty'])
def test_parse_component_node_select_operators(operator):
    node = _make_select_node(operator)
    result = _make_builder('color', FIELD_TYPE_SELECT)._parse_component_node(node)
    assert result is not None


def _valid_component():
    # An equals component with a literal value always produces a query.
    return ComponentNode(
        operator='equals',
        field='name',
        field_type=FIELD_TYPE_TEXT,
        inputs={'value': ConstantInput(value='alice')},
    )


def _droppable_component():
    # An equals component whose parameter value is not supplied resolves to
    # None, so the component is dropped.
    return ComponentNode(
        operator='equals',
        field='name',
        field_type=FIELD_TYPE_TEXT,
        inputs={'value': ParameterInput(value='missing')},
    )


def test_build_query_all_dropped_applies_no_extra_filter():
    builder = _make_builder('name', FIELD_TYPE_TEXT)
    builder.query_root = GroupNode(type='all', children=[_droppable_component()])
    sentinel = object()
    builder._get_initial_query = lambda: sentinel
    # No surviving conditions => return the base query untouched, never
    # apply .where(None) or a match-all empty bool.
    assert builder.build_query([]) is sentinel


def test_build_query_with_surviving_condition_adds_where_clause():
    builder = _make_builder('name', FIELD_TYPE_TEXT)
    builder.query_root = GroupNode(type='all', children=[_valid_component()])

    class FakeQuery:
        def where(self, clause):
            self.where_clause = clause
            return self

    fake = FakeQuery()
    builder._get_initial_query = lambda: fake
    assert builder.build_query([]) is fake
    assert fake.where_clause is not None


_VALUE_BY_FIELD_TYPE = {
    FIELD_TYPE_TEXT: 'alice',
    FIELD_TYPE_NUMBER: '5',
    FIELD_TYPE_DATE: '2020-01-01',
    FIELD_TYPE_DATETIME: '2020-01-01',
    FIELD_TYPE_SELECT: 'a',
}


def _inputs_for_operator(operator, field_type):
    if operator == 'within_distance':
        return {
            'point': ConstantInput(value='12.5 13.5'),
            'distance': ConstantInput(value='10'),
            'unit': ConstantInput(value=DISTANCE_UNITS[0]),
        }
    # Every non-geopoint operator resolves its value through the single
    # 'value' slot, which the builder reads unconditionally.
    return {'value': ConstantInput(value=_VALUE_BY_FIELD_TYPE[field_type])}


@pytest.mark.parametrize('field_type,operator', [
    (field_type, name)
    for field_type, operators in _OPERATOR_BY_TYPE.items()
    for name, _label in operators
])
def test_every_declared_operator_is_handled_by_builder(field_type, operator):
    node = ComponentNode(
        operator=operator,
        field='some_field',
        field_type=field_type,
        inputs=_inputs_for_operator(operator, field_type),
    )
    result = _make_builder('some_field', field_type)._parse_component_node(node)
    assert result is not None, (
        f"operator '{operator}' is declared for field type '{field_type}' "
        f"but _parse_component_node returned None"
    )


# --- Integration tests: build_query() executed against a real project_db table ---

class _FakeHelper:
    def __init__(self, domain):
        self.domain = domain
        self.config = None


def _make_case(case_json=None, **fields):
    return CommCareCase(
        case_id=fields.get('case_id', str(uuid.uuid4())),
        domain=fields.get('domain', 'test-sql-query-builder'),
        type=fields.get('type', 'patient'),
        name=fields.get('name', 'Test Case'),
        owner_id=fields.get('owner_id', 'owner1'),
        opened_on=fields.get('opened_on', datetime.datetime(2025, 1, 1)),
        closed_on=fields.get('closed_on', None),
        modified_on=fields.get('modified_on', datetime.datetime(2025, 6, 1)),
        closed=fields.get('closed', False),
        external_id=fields.get('external_id', ''),
        server_modified_on=fields.get('server_modified_on', datetime.datetime(2025, 6, 1)),
        case_json=case_json or {},
        indices=fields.get('indices', []),
    )


@use('db', project_db_table('test-sql-query-builder', 'patient', {
    'nickname': 'plain',
    'age': 'number',
}))
def test_build_query_runs_against_real_db():
    domain = 'test-sql-query-builder'
    send_to_project_db(domain, 'patient', [
        _make_case({'nickname': 'Alice', 'age': '30'}, case_id='c1'),
        _make_case({'nickname': 'Bob', 'age': '40'}, case_id='c2'),
    ])

    query_root = GroupNode(type='all', children=[
        ComponentNode(
            operator='equals',
            field='nickname',
            field_type=FIELD_TYPE_TEXT,
            inputs={'value': ConstantInput(value='Alice')},
        ),
    ])
    builder = CaseSearchEndpointSqlQueryBuilder(_FakeHelper(domain), 'patient', query_root)
    query = builder.build_query([])

    with get_project_db_engine().begin() as conn:
        rows = conn.execute(query).fetchall()

    assert [row.case_id for row in rows] == ['c1']


@use('db', project_db_table('test-sql-query-builder', 'patient', {
    'nickname': 'plain',
    'age': 'number',
}))
def test_build_query_no_matches_returns_empty():
    domain = 'test-sql-query-builder'
    send_to_project_db(domain, 'patient', [
        _make_case({'nickname': 'Alice', 'age': '30'}, case_id='c1'),
    ])

    query_root = GroupNode(type='all', children=[
        ComponentNode(
            operator='gt',
            field='age',
            field_type=FIELD_TYPE_NUMBER,
            inputs={'value': ConstantInput(value='100')},
        ),
    ])
    builder = CaseSearchEndpointSqlQueryBuilder(_FakeHelper(domain), 'patient', query_root)
    query = builder.build_query([])

    with get_project_db_engine().begin() as conn:
        rows = conn.execute(query).fetchall()

    assert rows == []
