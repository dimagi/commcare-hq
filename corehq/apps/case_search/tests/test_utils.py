from unittest.mock import patch

import pytest

from corehq.apps.case_search.endpoint_capability import FIELD_TYPE_GEOPOINT, FIELD_TYPE_TEXT
from corehq.apps.case_search.endpoint_query_spec import ComponentNode, ConstantInput, ParameterInput
from corehq.apps.case_search.utils import (
    CaseSearchEndpointQueryBuilder,
    CaseSearchProfiler,
    get_expanded_case_results,
)
from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_property_query, sounds_like_text_query
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
