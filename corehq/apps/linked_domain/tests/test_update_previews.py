from unittest import mock

from corehq.apps.linked_domain.local_accessors import get_enabled_previews
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_previews
from toggle.shortcuts import set_toggle

from corehq.feature_previews import FeaturePreview
from corehq.toggles import NAMESPACE_DOMAIN

TEST_PREVIEW = FeaturePreview(
    slug='test_preview',
    label='Test label',
    description='Test description',
)


@mock.patch('corehq.feature_previews.all_previews_by_name', mock.Mock(return_value={'TEST_PREVIEW': TEST_PREVIEW}))
class TestUpdatePreviews(BaseLinkedAppsTest):

    def tearDown(self):
        super(TestUpdatePreviews, self).tearDown()
        set_toggle('test_preview', self.domain_link.master_domain, False, NAMESPACE_DOMAIN)
        set_toggle('test_preview', self.domain_link.linked_domain, False, NAMESPACE_DOMAIN)

    def test_get_enabled_previews(self):
        set_toggle('test_preview', self.domain_link.master_domain, True, NAMESPACE_DOMAIN)
        enabled_previews = get_enabled_previews(self.domain_link.master_domain)
        self.assertEqual(['test_preview'], enabled_previews)

    def test_downstream_preview_enabled_in_local_link(self):
        set_toggle('test_preview', self.domain_link.master_domain, True, NAMESPACE_DOMAIN)
        update_previews(self.domain_link)
        self.assertTrue(TEST_PREVIEW.enabled(self.domain_link.linked_domain, NAMESPACE_DOMAIN))

    def test_downstream_preview_disabled_in_local_link(self):
        set_toggle('test_preview', self.domain_link.linked_domain, True, NAMESPACE_DOMAIN)
        set_toggle('test_preview', self.domain_link.master_domain, False, NAMESPACE_DOMAIN)
        update_previews(self.domain_link)
        self.assertFalse(TEST_PREVIEW.enabled(self.domain_link.linked_domain, NAMESPACE_DOMAIN))
