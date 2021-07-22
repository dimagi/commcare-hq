from unittest import mock

from corehq.apps.linked_domain.local_accessors import get_enabled_toggles
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_toggles
from toggle.shortcuts import set_toggle
from corehq.toggles import NAMESPACE_DOMAIN, StaticToggle, TAG_INTERNAL

TEST_TOGGLE = StaticToggle(
    'test_toggle',
    'This is for tests',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
)


@mock.patch('corehq.toggles.all_toggles_by_name', mock.Mock(return_value={'TEST_TOGGLE': TEST_TOGGLE}))
class TestUpdateToggles(BaseLinkedAppsTest):

    def tearDown(self):
        super(TestUpdateToggles, self).tearDown()
        set_toggle('test_toggle', self.domain_link.master_domain, False, NAMESPACE_DOMAIN)
        set_toggle('test_toggle', self.domain_link.linked_domain, False, NAMESPACE_DOMAIN)

    def test_get_enabled_toggles(self):
        set_toggle('test_toggle', self.domain_link.master_domain, True, NAMESPACE_DOMAIN)
        enabled_toggles = get_enabled_toggles(self.domain_link.master_domain)
        self.assertEqual(['test_toggle'], enabled_toggles)

    def test_downstream_toggle_enabled_in_local_link(self):
        set_toggle('test_toggle', self.domain_link.master_domain, True, NAMESPACE_DOMAIN)
        update_toggles(self.domain_link)
        self.assertTrue(TEST_TOGGLE.enabled(self.domain_link.linked_domain, NAMESPACE_DOMAIN))

    def test_downstream_toggle_not_disabled_in_local_link(self):
        set_toggle('test_toggle', self.domain_link.linked_domain, True, NAMESPACE_DOMAIN)
        set_toggle('test_toggle', self.domain_link.master_domain, False, NAMESPACE_DOMAIN)
        update_toggles(self.domain_link)
        self.assertTrue(TEST_TOGGLE.enabled(self.domain_link.linked_domain, NAMESPACE_DOMAIN))
