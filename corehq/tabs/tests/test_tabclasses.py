from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from corehq.apps.users.models import WebUser
from corehq.privileges import LITE_RELEASE_MANAGEMENT, RELEASE_MANAGEMENT
from corehq.tabs.tabclasses import MessagingTab, _get_release_management_items
from corehq.tabs.utils import path_starts_with_url

__test__ = {
    'url_starts_with_path': path_starts_with_url
}


class TestAccessToReleaseManagementTab(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser(username='test-username')

    def setUp(self):
        super().setUp()

        access_patcher = patch('corehq.tabs.tabclasses.can_user_access_linked_domains')
        self.mock_can_access = access_patcher.start()
        self.addCleanup(access_patcher.stop)

        privilege_patcher = patch('corehq.tabs.tabclasses.domain_has_privilege')
        self.mock_domain_has_privilege = privilege_patcher.start()
        self.addCleanup(privilege_patcher.stop)

        reverse_patcher = patch('corehq.tabs.tabclasses.reverse')
        self.mock_reverse = reverse_patcher.start()
        self.mock_reverse.return_value = 'dummy_url'
        self.addCleanup(reverse_patcher.stop)

    def test_returns_none_if_user_does_not_have_access(self):
        self.mock_can_access.return_value = False

        title, items = _get_release_management_items(self.user, "domain")

        self.assertFalse(title)
        self.assertFalse(items)

    def test_returns_erm_if_user_has_full_access(self):
        self.mock_can_access.return_value = True
        self.mock_domain_has_privilege.side_effect = lambda domain, privilege: privilege == RELEASE_MANAGEMENT

        title, items = _get_release_management_items(self.user, "domain")

        self.assertEqual(title, 'Enterprise Release Management')
        self.assertEqual(items[0]['title'], 'Linked Project Spaces')
        self.assertEqual(items[1]['title'], 'Linked Project Space History')

    def test_returns_mrm_if_user_has_lite_access(self):
        self.mock_can_access.return_value = True
        self.mock_domain_has_privilege.side_effect = lambda domain, privilege: privilege == LITE_RELEASE_MANAGEMENT

        title, items = _get_release_management_items(self.user, "domain")

        self.assertEqual(title, 'Multi-Environment Release Management')
        self.assertEqual(items[0]['title'], 'Linked Project Spaces')
        self.assertEqual(items[1]['title'], 'Linked Project Space History')


class TestMessagingTabDocumentTemplates(SimpleTestCase):
    """Document templates have their own permissions, independent of ``edit_messaging``"""

    def setUp(self):
        super().setUp()
        self.enterContext(patch('corehq.tabs.tabclasses.reverse', side_effect=lambda name, args=None: name))
        self.enterContext(patch('corehq.tabs.tabclasses.has_privilege', return_value=True))
        self.enterContext(patch('corehq.tabs.tabclasses.toggles.DOCUMENT_TEMPLATES.enabled', return_value=True))
        other_sections = ['messages', 'reminders', 'supply', 'contacts', 'settings', 'whatsapp', 'connect']
        self.enterContext(patch.multiple(MessagingTab, **{f'{name}_urls': [] for name in other_sections}))

    def _tab(self, permissions):
        user = Mock(
            has_permission=lambda domain, name, **kwargs: name in permissions,
            can_edit_messaging=lambda: 'edit_messaging' in permissions,
            is_commcare_user=lambda: False,
        )
        return MessagingTab(Mock(), domain='domain', couch_user=user, project=Mock(is_snapshot=False))

    def _sidebar_titles(self, tab):
        return [title for title, urls in tab.sidebar_items]

    def test_viewer_without_edit_messaging_sees_only_document_templates(self):
        tab = self._tab({'view_document_templates'})
        assert tab._is_viewable
        assert self._sidebar_titles(tab) == ['Document Templates']
        assert tab.url == 'document_templates'
        assert [item['url'] for item in tab.dropdown_items] == ['document_templates']

    def test_user_with_neither_permission_does_not_see_the_tab(self):
        assert not self._tab(set())._is_viewable

    def test_user_with_edit_messaging_sees_the_whole_section(self):
        tab = self._tab({'edit_messaging'})
        assert tab._is_viewable
        assert self._sidebar_titles(tab)[0] == 'Dashboard'
        assert 'Document Templates' not in self._sidebar_titles(tab)
        assert tab.url == '/a/domain/sms/'

    def test_user_with_both_permissions_gets_document_templates_in_the_section(self):
        tab = self._tab({'edit_messaging', 'view_document_templates'})
        assert self._sidebar_titles(tab)[0] == 'Dashboard'
        assert self._sidebar_titles(tab)[-1] == 'Document Templates'

    def test_toggle_off_hides_document_templates(self):
        with patch('corehq.tabs.tabclasses.toggles.DOCUMENT_TEMPLATES.enabled', return_value=False):
            assert not self._tab({'view_document_templates'})._is_viewable
