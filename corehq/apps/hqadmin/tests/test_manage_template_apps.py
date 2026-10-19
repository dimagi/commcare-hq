"""Access and rendering tests for the template app management page."""

from django.test import TestCase
from django.urls import reverse

from corehq.apps.users.models import WebUser


class TestManageTemplateAppsPage(TestCase):
    """Expose the page to superusers while keeping staff-only and ordinary users out."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.superuser = WebUser.create(None, 'template-page-superuser@dimagi.com', 'password', None, None,
                                      is_superuser=True, is_staff=True)
        cls.staff = WebUser.create(None, 'template-page-staff@dimagi.com', 'password', None, None, is_staff=True)
        cls.regular = WebUser.create(None, 'template-page-reader@dimagi.com', 'password', None, None)
        for user in [cls.superuser, cls.staff, cls.regular]:
            cls.addClassCleanup(user.delete, None, None)
        cls.url = reverse('manage_template_apps')

    def test_superuser_can_view_page(self):
        self.client.login(username=self.superuser.username, password='password')
        response = self.client.get(self.url)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'hqadmin/template_apps/manage_template_apps.html')
        self.assertContains(response, 'Manage Template Apps')

    def test_non_superusers_cannot_view_page(self):
        for user in [self.staff, self.regular, None]:
            self.client.logout()
            if user:
                self.client.login(username=user.username, password='password')
            response = self.client.get(self.url)
            assert response.status_code == 302
            assert response.url == reverse('no_permissions')
