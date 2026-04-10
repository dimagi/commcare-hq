from django.db import IntegrityError
from django.http import Http404
from django.test import SimpleTestCase, TestCase

from corehq.apps.case_search import endpoint_service
from corehq.apps.case_search.models import CaseSearchEndpoint
from corehq.apps.case_search.endpoint_capability import (
    _AUTO_VALUES,
    FIELD_TYPE_DATE,
    FIELD_TYPE_TEXT,
    get_operations_for_field_type,
)


DOMAIN = 'test-domain'
EMPTY_QUERY = {'type': 'and', 'children': []}
SAMPLE_QUERY = {
    'type': 'and',
    'children': [
        {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'parameter', 'ref': 'search_province'},
            },
        },
    ],
}
SAMPLE_PARAMS = [{'name': 'search_province', 'type': 'text'}]


class TestCreateEndpoint(TestCase):

    def test_creates_endpoint_and_first_version(self):
        endpoint = endpoint_service.create_endpoint(
            domain='test-domain',
            name='My Endpoint',
            target_type='project_db',
            target_name='patient',
            parameters=[{'name': 'q', 'type': 'text', 'required': True}],
            query={'type': 'and', 'children': []},
        )
        assert endpoint.current_version is not None
        assert endpoint.current_version.version_number == 1
        assert endpoint.current_version.parameters == [
            {'name': 'q', 'type': 'text', 'required': True}
        ]

    def test_raises_on_duplicate_name(self):
        endpoint_service.create_endpoint(
            domain='test-domain',
            name='Dup',
            target_type='project_db',
            target_name='patient',
            parameters=[],
            query={'type': 'and', 'children': []},
        )
        with self.assertRaises(IntegrityError):
            endpoint_service.create_endpoint(
                domain='test-domain',
                name='Dup',
                target_type='project_db',
                target_name='patient',
                parameters=[],
                query={'type': 'and', 'children': []},
            )


class TestSaveNewVersion(TestCase):

    def setUp(self):
        self.endpoint = endpoint_service.create_endpoint(
            domain='test-domain',
            name='Versioned',
            target_type='project_db',
            target_name='patient',
            parameters=[],
            query={'type': 'and', 'children': []},
        )

    def test_increments_version_number(self):
        v2 = endpoint_service.save_new_version(
            self.endpoint,
            parameters=[{'name': 'p', 'type': 'text', 'required': False}],
            query={'type': 'or', 'children': []},
        )
        assert v2.version_number == 2
        self.endpoint.refresh_from_db()
        assert self.endpoint.current_version == v2

    def test_previous_version_unchanged(self):
        v1 = self.endpoint.current_version
        endpoint_service.save_new_version(
            self.endpoint,
            parameters=[],
            query={'type': 'or', 'children': []},
        )
        v1.refresh_from_db()
        assert v1.version_number == 1
        assert v1.query == {'type': 'and', 'children': []}


class TestListEndpoints(TestCase):

    def test_returns_only_active_for_domain(self):
        endpoint_service.create_endpoint('d1', 'A', 'project_db', 'p', [], {'type': 'and', 'children': []})
        endpoint_service.create_endpoint('d1', 'B', 'project_db', 'p', [], {'type': 'and', 'children': []})
        endpoint_service.create_endpoint('d2', 'C', 'project_db', 'p', [], {'type': 'and', 'children': []})

        ep_b = CaseSearchEndpoint.objects.get(domain='d1', name='B')
        endpoint_service.deactivate_endpoint(ep_b)

        result = endpoint_service.list_endpoints('d1')
        assert list(result.values_list('name', flat=True)) == ['A']


class TestGetEndpoint(TestCase):

    def test_returns_endpoint_for_domain(self):
        ep = endpoint_service.create_endpoint('d1', 'X', 'project_db', 'p', [], {'type': 'and', 'children': []})
        fetched = endpoint_service.get_endpoint('d1', ep.id)
        assert fetched.pk == ep.pk

    def test_raises_404_wrong_domain(self):
        ep = endpoint_service.create_endpoint('d1', 'X', 'project_db', 'p', [], {'type': 'and', 'children': []})
        with self.assertRaises(Http404):
            endpoint_service.get_endpoint('d2', ep.id)


class TestDeactivateEndpoint(TestCase):

    def test_sets_is_active_false(self):
        ep = endpoint_service.create_endpoint('d1', 'Del', 'project_db', 'p', [], {'type': 'and', 'children': []})
        endpoint_service.deactivate_endpoint(ep)
        ep.refresh_from_db()
        assert ep.is_active is False


class TestValidateFilterSpec(SimpleTestCase):

    def setUp(self):
        self.capability = {
            'case_types': [{
                'name': 'patient',
                'fields': [
                    {
                        'name': 'province',
                        'type': FIELD_TYPE_TEXT,
                        'operations': get_operations_for_field_type(FIELD_TYPE_TEXT),
                    },
                    {
                        'name': 'dob',
                        'type': FIELD_TYPE_DATE,
                        'operations': get_operations_for_field_type(FIELD_TYPE_DATE),
                    },
                ],
            }],
            'auto_values': _AUTO_VALUES,
        }

    def test_valid_simple_spec(self):
        spec = {
            'type': 'and',
            'children': [{
                'type': 'component',
                'component': 'exact_match',
                'field': 'province',
                'inputs': {
                    'value': {'type': 'constant', 'value': 'ON'},
                },
            }],
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertEqual(errors, [])

    def test_valid_date_range_spec(self):
        spec = {
            'type': 'component',
            'component': 'date_range',
            'field': 'dob',
            'inputs': {
                'start': {'type': 'constant', 'value': '2000-01-01'},
                'end': {'type': 'auto_value', 'ref': 'today()'},
            },
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertEqual(errors, [])

    def test_invalid_root_type(self):
        spec = {'type': 'invalid'}
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertTrue(any('type' in e.lower() for e in errors))

    def test_unknown_field(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'nonexistent',
            'inputs': {
                'value': {'type': 'constant', 'value': 'x'},
            },
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertTrue(any('nonexistent' in e for e in errors))

    def test_incompatible_component_for_field(self):
        spec = {
            'type': 'component',
            'component': 'date_range',
            'field': 'province',  # text field, date_range is not valid
            'inputs': {
                'start': {'type': 'constant', 'value': '2000-01-01'},
                'end': {'type': 'constant', 'value': '2020-01-01'},
            },
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertTrue(any('date_range' in e for e in errors))

    def test_missing_required_input_slot(self):
        spec = {
            'type': 'component',
            'component': 'date_range',
            'field': 'dob',
            'inputs': {
                'start': {'type': 'constant', 'value': '2000-01-01'},
                # 'end' missing
            },
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertTrue(any('end' in e for e in errors))

    def test_parameter_ref_must_exist(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'parameter', 'ref': 'missing_param'},
            },
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertTrue(any('missing_param' in e for e in errors))

    def test_parameter_ref_valid(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'parameter', 'ref': 'search_province'},
            },
        }
        params = [{'name': 'search_province', 'type': 'text'}]
        errors = endpoint_service.validate_filter_spec(spec, params, 'patient', self.capability)
        self.assertEqual(errors, [])

    def test_invalid_auto_value_ref(self):
        spec = {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'auto_value', 'ref': 'nonexistent()'},
            },
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertTrue(any('nonexistent' in e for e in errors))

    def test_not_node_with_valid_child(self):
        spec = {
            'type': 'not',
            'child': {
                'type': 'component',
                'component': 'exact_match',
                'field': 'province',
                'inputs': {
                    'value': {'type': 'constant', 'value': 'ON'},
                },
            },
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertEqual(errors, [])

    def test_not_node_missing_child(self):
        spec = {'type': 'not'}
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertTrue(any('child' in e for e in errors))

    def test_nested_and_or(self):
        spec = {
            'type': 'and',
            'children': [
                {
                    'type': 'or',
                    'children': [{
                        'type': 'component',
                        'component': 'exact_match',
                        'field': 'province',
                        'inputs': {
                            'value': {'type': 'constant', 'value': 'ON'},
                        },
                    }],
                },
            ],
        }
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertEqual(errors, [])

    def test_empty_children_allowed(self):
        spec = {'type': 'and', 'children': []}
        errors = endpoint_service.validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertEqual(errors, [])
