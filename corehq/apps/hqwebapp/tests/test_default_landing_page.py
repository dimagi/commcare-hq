from contextlib import nullcontext

from django.test import Client, TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.app_manager.models import Application
from corehq.apps.cloudcare.views import FormplayerMain
from corehq.apps.dashboard.views import DomainDashboardView
from corehq.apps.domain.models import Domain
from corehq.apps.reports.views import MySavedReportsView
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import (
    CommCareUser,
    HqPermissions,
    UserRole,
    WebUser,
)
from corehq.util.test_utils import generate_cases, privilege_enabled

DOMAIN = 'temerant'


class TestDefaultLandingPages(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_users()
        cls.client = Client()

        cls.domain = DOMAIN
        cls.domain_object = Domain(name=cls.domain, is_active=True)
        cls.domain_object.save()

        cls.reports_role = UserRole.create(
            domain=cls.domain, name='reports-role', default_landing_page='reports',
            permissions=HqPermissions(view_reports=True),
        )
        cls.webapps_role = UserRole.create(
            domain=cls.domain, name='webapps-role', default_landing_page='webapps',
            permissions=HqPermissions(access_web_apps=True),
        )
        cls.downloads_role = UserRole.create(
            domain=cls.domain, name='downloads-role', default_landing_page='downloads',
            permissions=HqPermissions.max(),
        )
        cls.global_password = 'secret'

        # make an app because not having one changes the default dashboard redirect to the apps page
        app = Application.new_app(domain=cls.domain, name='sympathy')
        app.save()

    def _make_web_user(self, username, role=None, override_domain=None):
        domain = override_domain or self.domain
        web_user = WebUser.create(domain, username, self.global_password, None, None)
        web_user.eula.signed = True
        if role:
            web_user.set_role(domain, role.get_qualified_id())
        web_user.save()
        return web_user

    def _make_commcare_user(self, username, role=None, override_domain=None):
        domain = override_domain or self.domain
        web_user = CommCareUser.create(domain, username, self.global_password, None, None)
        web_user.eula.signed = True
        if role:
            web_user.set_role(domain, role.get_qualified_id())
        web_user.save()
        return web_user

    @classmethod
    def tearDownClass(cls):
        cls.domain_object.delete()

    def test_no_role_cant_access(self):
        user = self._make_web_user('elodin@theuniversity.com')
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        user.delete_domain_membership(self.domain)
        user.save()
        self.client.login(username=user.username, password=self.global_password)
        response = self.client.get(reverse("domain_homepage", args=[self.domain]), follow=True)
        self.assertEqual(response.status_code, 404)

    def test_formplayer_default_override(self):
        web_user = self._make_web_user('elodin@theuniversity.com', role=self.webapps_role)
        self.addCleanup(web_user.delete, self.domain, deleted_by=None)
        mobile_worker = self._make_commcare_user('kvothe')
        self.addCleanup(mobile_worker.delete, self.domain, deleted_by=None)
        for user in [web_user, mobile_worker]:
            self.client.login(username=user.username, password=self.global_password)

            response = self.client.get(reverse("domain_homepage", args=[self.domain]), follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(reverse(FormplayerMain.urlname, args=[self.domain]),
                             response.request['PATH_INFO'])


@generate_cases([
    (None, DomainDashboardView.urlname),
    ('reports_role', MySavedReportsView.urlname),
    ('webapps_role', FormplayerMain.urlname),
    ('downloads_role', DomainDashboardView.urlname),
    ('downloads_role', 'download_data_files', privileges.DATA_FILE_DOWNLOAD),
], TestDefaultLandingPages)
def test_web_user_landing_page(self, role, expected_urlname, privilege=None):
    if role is not None:
        role = getattr(self, role)
    user = self._make_web_user('elodin@theuniversity.com', role=role)
    self.addCleanup(user.delete, self.domain, deleted_by=None)
    self.client.login(username=user.username, password=self.global_password)

    context = privilege_enabled(privilege) if privilege else nullcontext()
    with context:
        url = reverse("domain_homepage", args=[self.domain])
        response = self.client.get(url, follow=True)
    self.assertEqual(response.status_code, 200)
    self.assertEqual(reverse(expected_urlname, args=[self.domain]),
                     response.request['PATH_INFO'])


@generate_cases([
    (None, FormplayerMain.urlname),
    ('reports_role', MySavedReportsView.urlname),
    ('webapps_role', FormplayerMain.urlname),
    ('downloads_role', FormplayerMain.urlname),
    ('downloads_role', 'download_data_files', privileges.DATA_FILE_DOWNLOAD),
], TestDefaultLandingPages)
def test_mobile_worker_landing_page(self, role, expected_urlname, privilege=None):
    if role is not None:
        role = getattr(self, role)
    user = self._make_commcare_user('kvothe', role=role)
    self.addCleanup(user.delete, self.domain, deleted_by=None)
    self.client.login(username=user.username, password=self.global_password)

    context = privilege_enabled(privilege) if privilege else nullcontext()
    with context:
        url = reverse("domain_homepage", args=[self.domain])
        response = self.client.get(url, follow=True)
    self.assertEqual(response.status_code, 200)
    self.assertEqual(reverse(expected_urlname, args=[self.domain]),
                     response.request['PATH_INFO'])
