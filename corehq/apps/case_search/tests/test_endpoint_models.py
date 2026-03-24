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
            name='find-patients',
            target_type='project_db',
            target_name='patient',
        )
        self.assertEqual(endpoint.domain, 'test-domain')
        self.assertEqual(endpoint.name, 'find-patients')
        self.assertTrue(endpoint.is_active)
        self.assertIsNone(endpoint.current_version)
        self.assertIsNotNone(endpoint.created_at)

    def test_unique_name_per_domain(self):
        CaseSearchEndpoint.objects.create(
            domain='test-domain',
            name='find-patients',
            target_type='project_db',
            target_name='patient',
        )
        with self.assertRaises(IntegrityError):
            CaseSearchEndpoint.objects.create(
                domain='test-domain',
                name='find-patients',
                target_type='project_db',
                target_name='patient',
            )

    def test_same_name_different_domains(self):
        CaseSearchEndpoint.objects.create(
            domain='domain-a',
            name='find-patients',
            target_type='project_db',
            target_name='patient',
        )
        endpoint_b = CaseSearchEndpoint.objects.create(
            domain='domain-b',
            name='find-patients',
            target_type='project_db',
            target_name='patient',
        )
        self.assertEqual(endpoint_b.domain, 'domain-b')


class TestCaseSearchEndpointVersion(TestCase):

    def setUp(self):
        self.endpoint = CaseSearchEndpoint.objects.create(
            domain='test-domain',
            name='find-patients',
            target_type='project_db',
            target_name='patient',
        )

    def test_create_version(self):
        version = CaseSearchEndpointVersion.objects.create(
            endpoint=self.endpoint,
            version_number=1,
            parameters=[{'name': 'province', 'type': 'text'}],
            query={'type': 'and', 'children': []},
        )
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.parameters, [{'name': 'province', 'type': 'text'}])
        self.assertIsNotNone(version.created_at)

    def test_unique_version_per_endpoint(self):
        CaseSearchEndpointVersion.objects.create(
            endpoint=self.endpoint,
            version_number=1,
            parameters=[],
            query={},
        )
        with self.assertRaises(IntegrityError):
            CaseSearchEndpointVersion.objects.create(
                endpoint=self.endpoint,
                version_number=1,
                parameters=[],
                query={},
            )

    def test_current_version_fk(self):
        version = CaseSearchEndpointVersion.objects.create(
            endpoint=self.endpoint,
            version_number=1,
            parameters=[],
            query={},
        )
        self.endpoint.current_version = version
        self.endpoint.save()
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.current_version, version)

    def test_versions_not_deleted_on_deactivate(self):
        CaseSearchEndpointVersion.objects.create(
            endpoint=self.endpoint,
            version_number=1,
            parameters=[],
            query={},
        )
        self.endpoint.is_active = False
        self.endpoint.save()
        self.assertEqual(self.endpoint.versions.count(), 1)
