from django.db import IntegrityError
from django.http import Http404
from django.test import TestCase

from corehq.apps.case_search import endpoint_service
from corehq.apps.case_search.models import CaseSearchEndpoint


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
