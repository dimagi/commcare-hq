from django.test import TestCase

import pytest

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
    add_endpoint_version,
)
from corehq.apps.linked_domain.case_search_endpoints import (
    create_linked_case_search_endpoint,
    update_linked_case_search_endpoint,
)
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.linked_domain.models import DomainLink

UPSTREAM = 'endpoints-upstream'
DOWNSTREAM = 'endpoints-downstream'


def _create_endpoint(domain, name='patients', case_type='patient', sql='SELECT 1'):
    endpoint = CaseSearchEndpoint.objects.create(domain=domain, name=name)
    add_endpoint_version(
        endpoint,
        action=CaseSearchEndpointVersion.Action.CREATE,
        created_by='someone@example.com',
        case_type=case_type,
        query={'type': 'all', 'children': []},
        parameters=[],
        dangerous_sql=sql,
    )
    return endpoint


class TestCreateLinkedCaseSearchEndpoint(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_link = DomainLink.link_domains(DOWNSTREAM, UPSTREAM)
        cls.addClassCleanup(cls.domain_link.delete)

    def test_copies_endpoint_and_current_version(self):
        upstream_endpoint = _create_endpoint(UPSTREAM)

        downstream_id = create_linked_case_search_endpoint(self.domain_link, upstream_endpoint.id)

        downstream = CaseSearchEndpoint.objects.get(id=downstream_id)
        assert downstream.domain == DOWNSTREAM
        assert downstream.name == 'patients'
        assert downstream.upstream_id == upstream_endpoint.id
        assert downstream.current_version.version_number == 1
        assert downstream.current_version.case_type == 'patient'
        assert downstream.current_version.dangerous_sql == 'SELECT 1'
        assert downstream.current_version.action == CaseSearchEndpointVersion.Action.CREATE

    def test_rejects_remote_link(self):
        upstream_endpoint = _create_endpoint(UPSTREAM)
        self.domain_link.remote_base_url = 'https://example.com'
        self.addCleanup(setattr, self.domain_link, 'remote_base_url', None)

        with pytest.raises(DomainLinkError, match='remote'):
            create_linked_case_search_endpoint(self.domain_link, upstream_endpoint.id)

    def test_rejects_name_already_used_downstream(self):
        upstream_endpoint = _create_endpoint(UPSTREAM)
        _create_endpoint(DOWNSTREAM)

        with pytest.raises(DomainLinkError, match='already exists'):
            create_linked_case_search_endpoint(self.domain_link, upstream_endpoint.id)

    def test_rejects_endpoint_from_another_domain(self):
        other_endpoint = _create_endpoint('somewhere-else')

        with pytest.raises(DomainLinkError, match='does not exist in the upstream domain'):
            create_linked_case_search_endpoint(self.domain_link, other_endpoint.id)


class TestUpdateLinkedCaseSearchEndpoint(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_link = DomainLink.link_domains(DOWNSTREAM, UPSTREAM)
        cls.addClassCleanup(cls.domain_link.delete)

    def setUp(self):
        super().setUp()
        self.upstream_endpoint = _create_endpoint(UPSTREAM)
        self.downstream_id = create_linked_case_search_endpoint(
            self.domain_link, self.upstream_endpoint.id
        )

    def _update_and_reload(self):
        update_linked_case_search_endpoint(self.domain_link, self.downstream_id)
        return CaseSearchEndpoint.objects.get(id=self.downstream_id)

    def _change_upstream_query(self):
        add_endpoint_version(
            self.upstream_endpoint,
            action=CaseSearchEndpointVersion.Action.UPDATE,
            created_by='someone@example.com',
            case_type='household',
            query={'type': 'all', 'children': []},
            parameters=[],
            dangerous_sql='SELECT 2',
        )

    def test_new_content_becomes_a_new_version(self):
        self._change_upstream_query()

        downstream = self._update_and_reload()

        assert downstream.current_version.version_number == 2
        assert downstream.current_version.case_type == 'household'
        assert downstream.current_version.dangerous_sql == 'SELECT 2'
        assert downstream.current_version.action == CaseSearchEndpointVersion.Action.UPDATE

    def test_unchanged_content_does_not_add_a_version(self):
        downstream = self._update_and_reload()

        assert downstream.current_version.version_number == 1
        assert downstream.versions.count() == 1

    def test_rename_does_not_add_a_version(self):
        self.upstream_endpoint.name = 'renamed'
        self.upstream_endpoint.save()

        downstream = self._update_and_reload()

        assert downstream.name == 'renamed'
        assert downstream.versions.count() == 1

    def test_deactivation_is_copied(self):
        self.upstream_endpoint.is_active = False
        self.upstream_endpoint.save()

        assert not self._update_and_reload().is_active

    def test_rejects_missing_downstream_endpoint(self):
        with pytest.raises(DomainLinkError, match='Linked endpoint could not be found'):
            update_linked_case_search_endpoint(self.domain_link, 0)

    def test_rejects_deleted_upstream_endpoint(self):
        self.upstream_endpoint.delete()

        with pytest.raises(DomainLinkError, match='Maybe it has been deleted'):
            update_linked_case_search_endpoint(self.domain_link, self.downstream_id)
