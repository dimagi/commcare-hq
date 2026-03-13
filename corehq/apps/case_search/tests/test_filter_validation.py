from django.test import TestCase

from corehq.apps.case_search.endpoint_service import validate_filter_spec


def _make_capability():
    return {
        'case_types': [{
            'name': 'patient',
            'fields': [
                {'name': 'province', 'type': 'text',
                 'operations': ['exact_match', 'is_empty']},
                {'name': 'age', 'type': 'number',
                 'operations': ['equals', 'gt', 'gte', 'lt', 'lte', 'is_empty']},
                {'name': 'dob', 'type': 'date',
                 'operations': ['before', 'after', 'date_range', 'is_empty']},
            ],
        }],
        'auto_values': {
            'date': [{'ref': 'today()', 'label': 'Today'}],
            'text': [{'ref': 'user.username', 'label': 'Username'}],
        },
        'component_input_schemas': {
            'exact_match': [{'name': 'value', 'type': 'text'}],
            'is_empty': [],
            'equals': [{'name': 'value', 'type': 'match_field'}],
            'gt': [{'name': 'value', 'type': 'number'}],
            'gte': [{'name': 'value', 'type': 'number'}],
            'lt': [{'name': 'value', 'type': 'number'}],
            'lte': [{'name': 'value', 'type': 'number'}],
            'before': [{'name': 'value', 'type': 'match_field'}],
            'after': [{'name': 'value', 'type': 'match_field'}],
            'date_range': [{'name': 'start', 'type': 'match_field'},
                           {'name': 'end', 'type': 'match_field'}],
        },
    }


PARAMS = [
    {'name': 'search_province', 'type': 'text', 'required': True},
    {'name': 'min_age', 'type': 'number', 'required': False},
]


class TestValidateFilterSpec(TestCase):

    def test_valid_simple_spec(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'parameter', 'ref': 'search_province'},
            },
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert errors == []

    def test_valid_and_group(self):
        spec = {
            'type': 'and',
            'children': [
                {
                    'type': 'component',
                    'component': 'is_empty',
                    'field': 'province',
                    'inputs': {},
                },
            ],
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert errors == []

    def test_unknown_field(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'nonexistent',
            'inputs': {
                'value': {'type': 'constant', 'value': 'x'},
            },
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert any('nonexistent' in e for e in errors)

    def test_incompatible_component(self):
        spec = {
            'type': 'component',
            'component': 'gt',
            'field': 'province',
            'inputs': {
                'value': {'type': 'constant', 'value': '10'},
            },
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert any('gt' in e for e in errors)

    def test_missing_required_input(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {},
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert any('value' in e for e in errors)

    def test_unknown_parameter_ref(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'parameter', 'ref': 'nonexistent_param'},
            },
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert any('nonexistent_param' in e for e in errors)

    def test_unknown_auto_value_ref(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'auto_value', 'ref': 'bogus()'},
            },
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert any('bogus()' in e for e in errors)

    def test_invalid_input_type(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'magic', 'value': 'x'},
            },
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert any('magic' in e for e in errors)

    def test_empty_and_is_valid(self):
        spec = {'type': 'and', 'children': []}
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert errors == []

    def test_nested_or_inside_and(self):
        spec = {
            'type': 'and',
            'children': [
                {
                    'type': 'or',
                    'children': [
                        {
                            'type': 'component',
                            'component': 'exact_match',
                            'field': 'province',
                            'inputs': {
                                'value': {'type': 'constant', 'value': 'ON'},
                            },
                        },
                    ],
                },
            ],
        }
        errors = validate_filter_spec(spec, _make_capability(), 'patient', PARAMS)
        assert errors == []

    def test_unknown_case_type(self):
        spec = {'type': 'and', 'children': []}
        errors = validate_filter_spec(spec, _make_capability(), 'unknown_type', PARAMS)
        assert any('unknown_type' in e for e in errors)
