from django.db import IntegrityError
from django.test import TestCase

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)


class TestCaseSearchEndpoint(TestCase):

    def test_create_endpoint(self):
        endpoint = CaseSearchEndpoint.objects.create(
            domain='test-domain',
            name='Test Endpoint',
            target_type='project_db',
            target_name='patient',
        )
        assert endpoint.is_active is True
        assert endpoint.current_version is None

    def test_name_unique_per_domain(self):
        CaseSearchEndpoint.objects.create(
            domain='test-domain',
            name='Duplicate',
            target_type='project_db',
            target_name='patient',
        )
        with self.assertRaises(IntegrityError):
            CaseSearchEndpoint.objects.create(
                domain='test-domain',
                name='Duplicate',
                target_type='project_db',
                target_name='patient',
            )

    def test_same_name_different_domains(self):
        CaseSearchEndpoint.objects.create(
            domain='domain-a',
            name='Same Name',
            target_type='project_db',
            target_name='patient',
        )
        endpoint_b = CaseSearchEndpoint.objects.create(
            domain='domain-b',
            name='Same Name',
            target_type='project_db',
            target_name='patient',
        )
        assert endpoint_b.pk is not None


class TestCaseSearchEndpointVersion(TestCase):

    def setUp(self):
        self.endpoint = CaseSearchEndpoint.objects.create(
            domain='test-domain',
            name='Versioned Endpoint',
            target_type='project_db',
            target_name='patient',
        )

    def test_create_first_version(self):
        version = CaseSearchEndpointVersion.objects.create(
            endpoint=self.endpoint,
            version_number=1,
            parameters=[{'name': 'q', 'type': 'text', 'required': True}],
            query={'type': 'and', 'children': []},
        )
        assert version.version_number == 1

    def test_version_number_unique_per_endpoint(self):
        CaseSearchEndpointVersion.objects.create(
            endpoint=self.endpoint,
            version_number=1,
            parameters=[],
            query={'type': 'and', 'children': []},
        )
        with self.assertRaises(IntegrityError):
            CaseSearchEndpointVersion.objects.create(
                endpoint=self.endpoint,
                version_number=1,
                parameters=[],
                query={'type': 'and', 'children': []},
            )
