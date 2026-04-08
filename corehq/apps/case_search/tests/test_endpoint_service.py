from django.test import TestCase

from corehq.apps.case_search.endpoint_capability import get_capability
from corehq.apps.case_search.endpoint_service import (
    create_endpoint,
    deactivate_endpoint,
    get_endpoint,
    get_version,
    list_endpoints,
    save_new_version,
    validate_filter_spec,
)
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
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

    def test_creates_endpoint_with_first_version(self):
        endpoint = create_endpoint(
            domain=DOMAIN,
            name='find-patients',
            target_type='project_db',
            target_name='patient',
            parameters=SAMPLE_PARAMS,
            query=EMPTY_QUERY,
        )
        self.assertEqual(endpoint.name, 'find-patients')
        self.assertIsNotNone(endpoint.current_version)
        self.assertEqual(endpoint.current_version.version_number, 1)
        self.assertEqual(endpoint.current_version.parameters, SAMPLE_PARAMS)
        self.assertEqual(endpoint.current_version.query, EMPTY_QUERY)

    def test_creates_active_endpoint(self):
        endpoint = create_endpoint(
            domain=DOMAIN,
            name='find-patients',
            target_type='project_db',
            target_name='patient',
            parameters=[],
            query=EMPTY_QUERY,
        )
        self.assertTrue(endpoint.is_active)


class TestSaveNewVersion(TestCase):

    def setUp(self):
        self.endpoint = create_endpoint(
            domain=DOMAIN,
            name='find-patients',
            target_type='project_db',
            target_name='patient',
            parameters=[],
            query=EMPTY_QUERY,
        )

    def test_increments_version_number(self):
        v2 = save_new_version(self.endpoint, SAMPLE_PARAMS, EMPTY_QUERY)
        self.assertEqual(v2.version_number, 2)

    def test_updates_current_version(self):
        v2 = save_new_version(self.endpoint, SAMPLE_PARAMS, EMPTY_QUERY)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.current_version, v2)

    def test_preserves_old_versions(self):
        save_new_version(self.endpoint, SAMPLE_PARAMS, EMPTY_QUERY)
        self.assertEqual(self.endpoint.versions.count(), 2)

    def test_sequential_version_numbers(self):
        save_new_version(self.endpoint, [], EMPTY_QUERY)
        v3 = save_new_version(self.endpoint, SAMPLE_PARAMS, EMPTY_QUERY)
        self.assertEqual(v3.version_number, 3)


class TestListEndpoints(TestCase):

    def test_returns_active_endpoints_for_domain(self):
        create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        create_endpoint(DOMAIN, 'ep-2', 'project_db', 'household', [], EMPTY_QUERY)
        create_endpoint('other-domain', 'ep-3', 'project_db', 'patient', [], EMPTY_QUERY)

        results = list(list_endpoints(DOMAIN))
        self.assertEqual(len(results), 2)
        names = {ep.name for ep in results}
        self.assertEqual(names, {'ep-1', 'ep-2'})

    def test_excludes_deactivated(self):
        endpoint = create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        deactivate_endpoint(endpoint)

        results = list(list_endpoints(DOMAIN))
        self.assertEqual(len(results), 0)


class TestGetEndpoint(TestCase):

    def test_returns_active_endpoint(self):
        created = create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        fetched = get_endpoint(DOMAIN, created.id)
        self.assertEqual(fetched.id, created.id)

    def test_raises_for_inactive(self):
        created = create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        deactivate_endpoint(created)
        with self.assertRaises(CaseSearchEndpoint.DoesNotExist):
            get_endpoint(DOMAIN, created.id)

    def test_raises_for_wrong_domain(self):
        created = create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        with self.assertRaises(CaseSearchEndpoint.DoesNotExist):
            get_endpoint('wrong-domain', created.id)


class TestGetVersion(TestCase):

    def test_returns_specific_version(self):
        endpoint = create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        save_new_version(endpoint, SAMPLE_PARAMS, EMPTY_QUERY)
        v1 = get_version(endpoint, 1)
        self.assertEqual(v1.version_number, 1)
        v2 = get_version(endpoint, 2)
        self.assertEqual(v2.version_number, 2)

    def test_raises_for_missing_version(self):
        endpoint = create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        with self.assertRaises(CaseSearchEndpointVersion.DoesNotExist):
            get_version(endpoint, 999)


class TestDeactivateEndpoint(TestCase):

    def test_sets_inactive(self):
        endpoint = create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        deactivate_endpoint(endpoint)
        endpoint.refresh_from_db()
        self.assertFalse(endpoint.is_active)

    def test_versions_preserved(self):
        endpoint = create_endpoint(DOMAIN, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY)
        save_new_version(endpoint, SAMPLE_PARAMS, EMPTY_QUERY)
        deactivate_endpoint(endpoint)
        self.assertEqual(endpoint.versions.count(), 2)


class TestValidateFilterSpec(TestCase):

    def setUp(self):
        self.case_type = CaseType.objects.create(
            domain=DOMAIN, name='patient',
        )
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='province',
            data_type=CaseProperty.DataType.PLAIN,
        )
        CaseProperty.objects.create(
            case_type=self.case_type,
            name='dob',
            data_type=CaseProperty.DataType.DATE,
        )
        self.capability = get_capability(DOMAIN)

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
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
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
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertEqual(errors, [])

    def test_invalid_root_type(self):
        spec = {'type': 'invalid'}
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
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
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
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
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
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
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
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
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
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
        errors = validate_filter_spec(spec, params, 'patient', self.capability)
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
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertTrue(any('nonexistent' in e for e in errors))

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
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertEqual(errors, [])

    def test_empty_children_allowed(self):
        spec = {'type': 'and', 'children': []}
        errors = validate_filter_spec(spec, [], 'patient', self.capability)
        self.assertEqual(errors, [])
