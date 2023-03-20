from django.http import HttpRequest
from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.reports.filters.controllers import (
    EnterpriseUserOptionsController,
)
from corehq.apps.reports.filters.users import EnterpriseUserFilter
from corehq.apps.users.models import CommCareUser, WebUser


@es_test(requires=[user_adapter], setup_class=True)
class BaseEnterpriseUserFilterTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up domains
        cls.domains = [
            create_domain('state'),
            create_domain('county'),
            create_domain('staging'),
        ]

        # Set up users
        cls.web_user = WebUser.create(
            'state', 'webu', 'badpassword', None, None, email='e@aol.com', is_admin=True)
        cls.web_user.add_domain_membership('county')
        cls.web_user.add_domain_membership('staging')
        cls.web_user.save()

        cls.mobile_users = [
            CommCareUser.create('state', "state_u", "123", None, None),
            CommCareUser.create("county", "county_u", "123", None, None),
            CommCareUser.create("staging", "staging_u", "123", None, None),
        ]

        # Set up permissions
        create_enterprise_permissions(cls.web_user.username, 'state', ['county'], ['staging'])

        for user_obj in cls.mobile_users:
            user_adapter.index(
                user_obj,
                refresh=True
            )

    @classmethod
    def tearDownClass(cls):
        for user in cls.mobile_users + [cls.web_user]:
            user.delete('state', deleted_by=None)
        for domain_obj in cls.domains:
            Domain.get_db().delete_doc(domain_obj)
        super().tearDownClass()


class EnterpriseUserFilterTest(BaseEnterpriseUserFilterTest):
    def test_active_users_from_source_domain(self):
        self._check_user_results('state', ['state_u', 'county_u'])

    def test_active_users_from_enterprise_controlled_domain(self):
        self._check_user_results('county', ['county_u'])

    def test_active_users_from_other_domain(self):
        self._check_user_results('staging', ['staging_u'])

    def _check_user_results(self, query_domain, expected_usernames):
        mobile_user_and_group_slugs = ['t__0']
        user_query = EnterpriseUserFilter.user_es_query(
            query_domain,
            mobile_user_and_group_slugs,
            self.web_user,
        )
        usernames = user_query.values_list('username', flat=True)
        self.assertCountEqual(usernames, expected_usernames)


class EnterpriseUserOptionsControllerTest(BaseEnterpriseUserFilterTest):
    def test_active_users_from_source_domain(self):
        self._check_user_results('state', [('state_u', 'state'), ('county_u', 'county')])

    def test_active_users_from_enterprise_controlled_domain(self):
        self._check_user_results('county', [('county_u', 'county')])

    def test_active_users_from_other_domain(self):
        self._check_user_results('staging', [('staging_u', 'staging')])

    def test_active_users_from_source_domain_location_restricted(self):
        controller = self.get_controller('state', can_access_all_locations=False)
        self._check_controller_results(controller, [])

    def get_controller(self, domain, can_access_all_locations=False):
        return EnterpriseUserOptionsController(
            _make_request(domain, self.web_user, can_access_all_locations), domain, ''
        )

    def _check_user_results(self, query_domain, expected_usernames):
        controller = self.get_controller(query_domain, can_access_all_locations=True)
        self._check_controller_results(controller, expected_usernames)

    def _check_controller_results(self, controller, expected_usernames):
        options = [
            option['text'] for option in controller.get_options()[1]
        ]
        self.assertCountEqual(options, [f"{u} [Active Mobile Worker in '{d}']" for u, d in expected_usernames])


def _make_request(domain, couch_user, can_access_all_locations=False):
    request = HttpRequest()
    request.method = 'GET'
    request.domain = domain
    request.couch_user = couch_user
    request.can_access_all_locations = can_access_all_locations
    return request
