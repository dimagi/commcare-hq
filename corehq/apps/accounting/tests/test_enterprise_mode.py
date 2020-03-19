from django.test import override_settings

from corehq import privileges
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import (
    clear_plan_version_cache,
    domain_has_privilege,
)
from corehq.apps.domain.shortcuts import create_domain

ADVANCED_PRIVILEGE = privileges.CUSTOM_BRANDING  # chosen arbitrarily, feel free to change


class TestEnterpriseMode(DomainSubscriptionMixin, BaseAccountingTest):

    def setUp(self):
        self.domain_obj = create_domain('test_enterprise_mode')

    def tearDown(self):
        self.domain_obj.delete()
        domain_has_privilege.clear(self.domain_obj.name, ADVANCED_PRIVILEGE)

    def test_standard_cant_access_advanced(self):
        self.setup_subscription(self.domain_obj.name, SoftwarePlanEdition.STANDARD)
        self.addCleanup(self.teardown_subscriptions)
        self.addCleanup(clear_plan_version_cache)
        self.assertFalse(self.domain_obj.has_privilege(ADVANCED_PRIVILEGE))

    def test_no_plan_cant_access_anything(self):
        self.assertFalse(self.domain_obj.has_privilege(ADVANCED_PRIVILEGE))

    def test_enterprise_can_access_anything(self):
        with override_settings(ENTERPRISE_MODE=True):
            self.assertTrue(self.domain_obj.has_privilege(ADVANCED_PRIVILEGE))
