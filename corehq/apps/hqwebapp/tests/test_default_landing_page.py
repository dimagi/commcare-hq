from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import reverse
from django.test import TestCase, Client
from corehq.apps.app_manager.models import Application
from corehq.apps.cloudcare.views import FormplayerMain
from corehq.apps.dashboard.views import DomainDashboardView
from corehq.apps.domain.models import Domain
from corehq.apps.reports.views import MySavedReportsView
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import UserRole, WebUser, Permissions, CommCareUser
from corehq.util.test_utils import generate_cases, flag_enabled


DOMAIN = 'temerant'


class TestDefaultLandingPages(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_users()
        cls.client = Client()

        cls.domain = DOMAIN
        cls.domain_object = Domain(name=cls.domain, is_active=True)
        cls.domain_object.save()

        cls.reports_role = UserRole(
            domain=cls.domain, name='reports-role', default_landing_page='reports',
            permissions=Permissions(view_reports=True),
        )
        cls.reports_role.save()
        cls.webapps_role = UserRole(
            domain=cls.domain, name='webapps-role', default_landing_page='webapps',
            permissions=Permissions(edit_data=True),
        )
        cls.webapps_role.save()
        cls.global_password = 'secret'

        # make an app because not having one changes the default dashboard redirect to the apps page
        app = Application.new_app(domain=cls.domain, name='sympathy')
        app.save()

    def _make_web_user(self, username, role=None, override_domain=None):
        domain = override_domain or self.domain
        web_user = WebUser.create(domain, username, self.global_password)
        web_user.eula.signed = True
        if role:
            web_user.set_role(domain, role.get_qualified_id())
        web_user.save()
        return web_user

    def _make_commcare_user(self, username, role=None, override_domain=None):
        domain = override_domain or self.domain
        web_user = CommCareUser.create(domain, username, self.global_password)
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
        self.addCleanup(user.delete)
        user.delete_domain_membership(self.domain)
        user.save()
        self.client.login(username=user.username, password=self.global_password)
        response = self.client.get(reverse("domain_homepage", args=[self.domain]), follow=True)
        self.assertEqual(response.status_code, 404)

    def test_formplayer_default_override(self):
        web_user = self._make_web_user('elodin@theuniversity.com', role=self.webapps_role)
        self.addCleanup(web_user.delete)
        mobile_worker = self._make_commcare_user('kvothe')
        self.addCleanup(mobile_worker.delete)
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
], TestDefaultLandingPages)
def test_web_user_landing_page(self, role, expected_urlname, extra_url_args=None):
    if role is not None:
        role = getattr(self, role)
    extra_url_args = extra_url_args or []
    user = self._make_web_user('elodin@theuniversity.com', role=role)
    self.addCleanup(user.delete)
    self.client.login(username=user.username, password=self.global_password)

    response = self.client.get(reverse("domain_homepage", args=[self.domain]), follow=True)
    self.assertEqual(response.status_code, 200)
    self.assertEqual(reverse(expected_urlname, args=[self.domain] + extra_url_args),
                     response.request['PATH_INFO'])


@generate_cases([
    (None, FormplayerMain.urlname),
    ('reports_role', MySavedReportsView.urlname),
    ('webapps_role', FormplayerMain.urlname),
], TestDefaultLandingPages)
def test_mobile_worker_landing_page(self, role, expected_urlname, extra_url_args=None):
    if role is not None:
        role = getattr(self, role)
    extra_url_args = extra_url_args or []
    user = self._make_commcare_user('kvothe', role=role)
    self.addCleanup(user.delete)
    self.client.login(username=user.username, password=self.global_password)

    response = self.client.get(reverse("domain_homepage", args=[self.domain]), follow=True)
    self.assertEqual(response.status_code, 200)
    self.assertEqual(reverse(expected_urlname, args=[self.domain] + extra_url_args),
                     response.request['PATH_INFO'])
