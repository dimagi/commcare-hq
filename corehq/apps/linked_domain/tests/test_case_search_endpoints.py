from datetime import datetime

from django.test import TestCase

import pytest
from time_machine import travel

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)
from corehq.apps.linked_domain.case_search_endpoints import (
    _sync_active_state,
    update_linked_case_search_endpoint,
)
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.linked_domain.models import DomainLink

UPSTREAM = 'endpoints-upstream'
DOWNSTREAM = 'endpoints-downstream'


def _create_endpoint(domain, name='patients', **version_fields):
    endpoint = CaseSearchEndpoint.objects.create(domain=domain, name=name)
    _add_version(endpoint, action=CaseSearchEndpointVersion.Action.CREATE, **version_fields)
    return endpoint


def _add_version(endpoint, action=CaseSearchEndpointVersion.Action.UPDATE,
                 case_type='patient', sql='SELECT 1'):
    current = endpoint.current_version
    endpoint.current_version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=current.version_number + 1 if current else 1,
        action=action,
        created_by='someone@example.com',
        case_type=case_type,
        query={'type': 'all', 'children': []},
        parameters=[],
        dangerous_sql=sql,
    )
    endpoint.save(update_fields=['current_version'])


def _deactivate(endpoint):
    endpoint.is_active = False
    endpoint.deactivated_on = datetime.utcnow()
    endpoint.deactivated_by = 'deactivator@example.com'
    endpoint.save()


class DomainLinkTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_link = DomainLink.link_domains(DOWNSTREAM, UPSTREAM)
        cls.addClassCleanup(cls.domain_link.delete)


class TestFirstLinkCreatesDownstreamEndpoint(DomainLinkTestCase):

    def test_copies_endpoint_and_current_version(self):
        upstream_endpoint = _create_endpoint(UPSTREAM)

        update_linked_case_search_endpoint(self.domain_link, upstream_endpoint.id)

        downstream = CaseSearchEndpoint.objects.get(domain=DOWNSTREAM)
        assert downstream.name == 'patients'
        assert downstream.upstream_id == upstream_endpoint.id
        assert downstream.current_version.version_number == 1
        assert downstream.current_version.case_type == 'patient'
        assert downstream.current_version.dangerous_sql == 'SELECT 1'
        assert downstream.current_version.action == CaseSearchEndpointVersion.Action.CREATE
        assert downstream.current_version.created_by == 'someone@example.com'

    def test_rejects_remote_link(self):
        upstream_endpoint = _create_endpoint(UPSTREAM)
        self.domain_link.remote_base_url = 'https://example.com'
        self.addCleanup(setattr, self.domain_link, 'remote_base_url', None)

        with pytest.raises(DomainLinkError, match='remote'):
            update_linked_case_search_endpoint(self.domain_link, upstream_endpoint.id)

    def test_rejects_endpoint_from_another_domain(self):
        other_endpoint = _create_endpoint('somewhere-else')

        with pytest.raises(DomainLinkError, match='does not exist in the upstream domain'):
            update_linked_case_search_endpoint(self.domain_link, other_endpoint.id)


class TestLaterLinksUpdateDownstreamEndpoint(DomainLinkTestCase):

    def setUp(self):
        super().setUp()
        self.upstream_endpoint = _create_endpoint(UPSTREAM)
        update_linked_case_search_endpoint(self.domain_link, self.upstream_endpoint.id)

    def _update_and_reload(self):
        update_linked_case_search_endpoint(self.domain_link, self.upstream_endpoint.id)
        return CaseSearchEndpoint.objects.get(domain=DOWNSTREAM)

    def test_new_versions_are_copied_with_upstream_numbers(self):
        _add_version(self.upstream_endpoint)
        _add_version(self.upstream_endpoint, case_type='household', sql='SELECT 2')

        downstream = self._update_and_reload()

        version_numbers = downstream.versions.order_by('version_number').values_list('version_number', flat=True)
        assert list(version_numbers) == [1, 3]
        assert downstream.current_version.version_number == 3
        assert downstream.current_version.case_type == 'household'
        assert downstream.current_version.dangerous_sql == 'SELECT 2'
        assert downstream.current_version.action == CaseSearchEndpointVersion.Action.UPDATE

    def test_rename_does_not_add_a_version(self):
        self.upstream_endpoint.name = 'renamed'
        self.upstream_endpoint.save()

        downstream = self._update_and_reload()

        assert downstream.name == 'renamed'
        assert downstream.versions.count() == 1

    def test_rejects_rename_to_name_used_downstream(self):
        _create_endpoint(DOWNSTREAM, name='taken')
        self.upstream_endpoint.name = 'taken'
        self.upstream_endpoint.save()

        with pytest.raises(DomainLinkError, match='conflicts with an existing endpoint'):
            update_linked_case_search_endpoint(self.domain_link, self.upstream_endpoint.id)

    def test_deactivation_is_stamped(self):
        _deactivate(self.upstream_endpoint)

        downstream = self._update_and_reload()

        assert not downstream.is_active
        assert downstream.deactivated_on is not None
        assert downstream.deactivated_by == 'deactivator@example.com'


EARLIER = datetime(2026, 1, 1)
NOW = datetime(2026, 2, 1)


def _unsaved_endpoint(is_active=True, deactivated_on=None, deactivated_by=''):
    return CaseSearchEndpoint(is_active=is_active, deactivated_on=deactivated_on, deactivated_by=deactivated_by)


UPSTREAM_INACTIVE = {'is_active': False, 'deactivated_on': EARLIER, 'deactivated_by': 'deactivator@example.com'}
DOWNSTREAM_INACTIVE = {'is_active': False, 'deactivated_on': EARLIER, 'deactivated_by': 'someone@example.com'}


@travel(NOW, tick=False)
@pytest.mark.parametrize('upstream, downstream, expected', [
    ({}, {}, (True, None, '')),
    ({}, DOWNSTREAM_INACTIVE, (True, None, '')),
    (UPSTREAM_INACTIVE, {}, (False, NOW, 'deactivator@example.com')),
    (UPSTREAM_INACTIVE, DOWNSTREAM_INACTIVE, (False, EARLIER, 'someone@example.com')),
])
def test_sync_active_state(upstream, downstream, expected):
    endpoint = _unsaved_endpoint(**downstream)
    _sync_active_state(_unsaved_endpoint(**upstream), endpoint)
    assert (endpoint.is_active, endpoint.deactivated_on, endpoint.deactivated_by) == expected
