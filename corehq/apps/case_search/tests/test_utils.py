from unittest.mock import patch

import pytest

from corehq.apps.case_search.endpoint_capability import (
    _OPERATOR_BY_TYPE,
    FIELD_TYPE_DATE,
    FIELD_TYPE_DATETIME,
    FIELD_TYPE_GEOPOINT,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_SELECT,
    FIELD_TYPE_TEXT,
)
from corehq.apps.es.queries import DISTANCE_UNITS
from corehq.apps.case_search.endpoint_query_spec import (
    ComponentNode,
    ConstantInput,
    GroupNode,
    ParameterInput,
)
from corehq.apps.case_search.utils import (
    CaseSearchEndpointQueryBuilder,
    CaseSearchProfiler,
    get_expanded_case_results,
)
from corehq.apps.case_search.xpath_functions.query_functions import date_permutations
from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import (
    case_property_date_range,
    case_property_query,
    sounds_like_text_query,
)
from corehq.form_processor.models import CommCareCase


@patch("corehq.apps.case_search.utils._get_case_search_cases")
def test_get_expanded_case_results(get_cases_mock):
    cases = [
        CommCareCase(case_json={}),
        CommCareCase(case_json={"potential_duplicate_id": "123"}),
        CommCareCase(case_json={"potential_duplicate_id": "456"}),
        CommCareCase(case_json={"potential_duplicate_id": ""}),
        CommCareCase(case_json={"potential_duplicate_id": None}),
    ]
    helper = None
    get_expanded_case_results(helper, "potential_duplicate_id", cases)
    get_cases_mock.assert_called_with(helper, {"123", "456"})


def test_profiler_search_class():
    profiler = CaseSearchProfiler()
    assert profiler.search_class == CaseSearchES


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
        field_type=FIELD_TYPE_GEOPOINT,
        inputs=inputs,
    )


def _make_builder():
    builder = CaseSearchEndpointQueryBuilder.__new__(CaseSearchEndpointQueryBuilder)
    builder.param_values = {}
    return builder


def test_parse_component_node_geopoint_within_distance():
    node = _make_geopoint_node()
    result = _make_builder()._parse_component_node(node)
    assert result is not None


@pytest.mark.parametrize('missing_input', ['point', 'distance', 'unit'])
def test_parse_component_node_geopoint_missing_input_returns_none(missing_input):
    kwargs = {missing_input: None}
    node = _make_geopoint_node(**kwargs)
    result = _make_builder()._parse_component_node(node)
    assert result is None


@pytest.mark.parametrize('bad_point,bad_distance,bad_unit', [
    ('not-a-coordinate', '10', 'kilometers'),
    ('12.5 13.5', 'not-a-number', 'kilometers'),
    ('12.5 13.5', '10', 'parsecs'),
])
def test_parse_component_node_geopoint_invalid_values_return_none(bad_point, bad_distance, bad_unit):
    node = _make_geopoint_node(point=bad_point, distance=bad_distance, unit=bad_unit)
    result = _make_builder()._parse_component_node(node)
    assert result is None


def test_parse_component_node_geopoint_parameter_input():
    node = ComponentNode(
        operator='within_distance',
        field='gps_field',
        field_type=FIELD_TYPE_GEOPOINT,
        inputs={
            'point': ParameterInput(value='my_point'),
            'distance': ConstantInput(value='5'),
            'unit': ConstantInput(value='miles'),
        },
    )
    builder = _make_builder()
    builder.param_values = {'my_point': '10.0 20.0'}
    result = builder._parse_component_node(node)
    assert result is not None


def test_parse_component_node_geopoint_missing_parameter_value_returns_none():
    node = ComponentNode(
        operator='within_distance',
        field='gps_field',
        field_type=FIELD_TYPE_GEOPOINT,
        inputs={
            'point': ParameterInput(value='my_point'),
            'distance': ConstantInput(value='5'),
            'unit': ConstantInput(value='miles'),
        },
    )
    builder = _make_builder()
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


def test_parse_component_node_text_fuzzy():
    node = _make_text_node('fuzzy')
    result = _make_builder()._parse_component_node(node)
    assert result == case_property_query('name', 'alice', fuzzy=True)


def test_parse_component_node_text_phonetic():
    node = _make_text_node('phonetic')
    result = _make_builder()._parse_component_node(node)
    assert result == sounds_like_text_query('name', 'alice')


def test_parse_component_node_text_fuzzy_differs_from_exact():
    fuzzy = _make_builder()._parse_component_node(_make_text_node('fuzzy'))
    exact = _make_builder()._parse_component_node(_make_text_node('equals'))
    assert fuzzy != exact


@pytest.mark.parametrize('operator', ['fuzzy', 'phonetic'])
def test_parse_component_node_text_missing_parameter_value_returns_none(operator):
    node = ComponentNode(
        operator=operator,
        field='name',
        field_type=FIELD_TYPE_TEXT,
        inputs={'value': ParameterInput(value='search_term')},
    )
    builder = _make_builder()
    builder.param_values = {}  # parameter not supplied
    result = builder._parse_component_node(node)
    assert result is None


def _make_date_node(operator, value='2020-01-01'):
    return ComponentNode(
        operator=operator,
        field='dob',
        field_type=FIELD_TYPE_DATE,
        inputs={'value': ConstantInput(value=value)},
    )


@pytest.mark.parametrize('operator', ['lt', 'gt', 'lte', 'gte'])
def test_parse_component_node_date_ranges(operator):
    result = _make_builder()._parse_component_node(_make_date_node(operator))
    assert result == case_property_date_range('dob', **{operator: '2020-01-01'})


def test_parse_component_node_fuzzy_date():
    result = _make_builder()._parse_component_node(_make_date_node('fuzzy_date'))
    assert result == case_property_query(
        'dob', date_permutations('2020-01-01'), boost_first=True
    )


def test_parse_component_node_fuzzy_date_invalid_returns_none():
    node = _make_date_node('fuzzy_date', value='not-a-date')
    result = _make_builder()._parse_component_node(node)
    assert result is None


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


@pytest.mark.parametrize('group_type', ['all', 'any', 'none'])
def test_parse_query_group_with_all_children_dropped_returns_none(group_type):
    node = GroupNode(
        type=group_type,
        children=[_droppable_component(), _droppable_component()],
    )
    assert _make_builder()._parse_query(node) is None


def test_parse_query_drops_empty_nested_group_in_any():
    # Reproduces the match-all bug: an empty nested `all` group (all its
    # children dropped) must not survive inside an `any`/OR as an empty bool.
    builder = _make_builder()
    empty_nested = GroupNode(type='all', children=[_droppable_component()])
    with_empty = GroupNode(type='any', children=[_valid_component(), empty_nested])
    without_empty = GroupNode(type='any', children=[_valid_component()])
    assert builder._parse_query(with_empty) == builder._parse_query(without_empty)


def test_parse_query_keeps_only_surviving_children():
    builder = _make_builder()
    mixed = GroupNode(type='all', children=[_valid_component(), _droppable_component()])
    only_valid = GroupNode(type='all', children=[_valid_component()])
    assert builder._parse_query(mixed) == builder._parse_query(only_valid)


def test_build_query_all_dropped_applies_no_extra_filter():
    builder = _make_builder()
    builder.query_root = GroupNode(type='all', children=[_droppable_component()])
    sentinel = object()
    builder._get_initial_search_es = lambda: sentinel
    # No surviving conditions => return the base query untouched, never
    # add_query(None) or a match-all empty bool.
    assert builder.build_query([]) is sentinel


def test_build_query_with_surviving_condition_adds_query():
    builder = _make_builder()
    builder.query_root = GroupNode(type='all', children=[_valid_component()])

    class FakeES:
        def add_query(self, query, clause):
            self.added_query = query
            return self

    fake = FakeES()
    builder._get_initial_search_es = lambda: fake
    assert builder.build_query([]) is fake
    assert fake.added_query is not None


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
    result = _make_builder()._parse_component_node(node)
    assert result is not None, (
        f"operator '{operator}' is declared for field type '{field_type}' "
        f"but _parse_component_node returned None"
    )
