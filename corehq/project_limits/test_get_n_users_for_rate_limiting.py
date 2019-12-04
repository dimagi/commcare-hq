from django.test import TestCase

from corehq.apps.accounting.bootstrap.config.testing import BOOTSTRAP_CONFIG_TESTING
from corehq.apps.accounting.models import SoftwarePlanEdition, FeatureType
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.project_limits.rate_limiter import get_n_users_for_rate_limiting


class GetNUsersForRateLimitingTest(TestCase, DomainSubscriptionMixin):

    def test_no_subscription(self):
        domain = 'domain-no-subscription'
        domain_obj = create_domain(domain)
        self.addCleanup(domain_obj.delete)

        get_n_users_for_rate_limiting.clear(domain)
        self.assertEqual(get_n_users_for_rate_limiting(domain), 0)

        self._set_n_users(domain, 1)

        get_n_users_for_rate_limiting.clear(domain)
        self.assertEqual(get_n_users_for_rate_limiting(domain), 1)

    def test_with_subscription(self):

        domain = 'domain-with-subscription'

        def _setup():
            domain_obj = create_domain(domain)
            self.setup_subscription(domain_obj.name, SoftwarePlanEdition.ADVANCED)
            self.addCleanup(lambda: self.teardown_subscription(domain))
            self.addCleanup(domain_obj.delete)
            assert CommCareUser.total_by_domain(domain, is_active=True) == 0

        def _get_included_in_subscription():
            n = (
                BOOTSTRAP_CONFIG_TESTING[(SoftwarePlanEdition.ADVANCED, False, False)]
                ['feature_rates'][FeatureType.USER]['monthly_limit']
            )
            assert n == 8
            return n

        _setup()

        # With no real users, it's the number of users in the subscription
        get_n_users_for_rate_limiting.clear(domain)
        self.assertEqual(get_n_users_for_rate_limiting(domain),
                         _get_included_in_subscription())

        self._set_n_users(domain, 9)

        # With more users than included in subscription, it's the number of users
        get_n_users_for_rate_limiting.clear(domain)
        self.assertEqual(get_n_users_for_rate_limiting(domain), 9)

    def _set_n_users(self, domain, n_users):
        start_n_users = CommCareUser.total_by_domain(domain, is_active=True)
        assert n_users >= start_n_users, 'this helper can only add users'

        for i in range(start_n_users, n_users):
            user = CommCareUser.create(domain, format_username('user{}'.format(i), domain),
                                       password='123')
            user.is_active = True
            user.save()
            self.addCleanup(user.delete)
        assert CommCareUser.total_by_domain(domain, is_active=True) == n_users
