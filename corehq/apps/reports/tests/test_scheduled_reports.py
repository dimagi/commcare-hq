from contextlib import contextmanager

from django.test import TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.locations.tests.util import setup_locations_and_types
from corehq.apps.reports.views import ScheduledReportsView
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import HqPermissions, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.util.test_utils import disable_quickcache, privilege_enabled


@es_test(requires=[
    case_search_adapter,
    form_adapter,
    user_adapter,
], setup_class=True)
@disable_quickcache
@privilege_enabled(privileges.API_ACCESS)
class TestLocationRestrictedScheduledReportViews(TestCase):
    domain = 'test-report-scheduling'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = bootstrap_domain(cls.domain)
        location_types, locations = setup_locations_and_types(
            cls.domain,
            location_types=['city'],
            stock_tracking_types=[],
            locations=[('Bhopal', []), ('Delhi', [])],
        )

        cls.user_location = locations['Bhopal']

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.domain_obj.delete()
        delete_all_users()

    def test_location_restricted_user_can_access_reports_home_view(self):
        with self._get_web_user_with_permissions_added():
            url = reverse('reports_home', args=(self.domain,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)

    def test_location_restricted_user_can_access_scheduled_report_view(self):
        with self._get_web_user_with_permissions_added():
            url = reverse(ScheduledReportsView.urlname, args=(self.domain,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_location_restricted_user_can_delete_scheduled_report(self):
        with self._get_web_user_with_permissions_added() as user:
            config = self.create_report_config(self.domain, user._id)
            rn = self.create_report_notification([config], owner_id=user._id)
            url = reverse('delete_scheduled_report', args=(self.domain, rn._id))
            response = self.client.post(url)
            # Assert that forbidden error code is not received
            self.assertNotEqual(response.status_code, 403)
            # Assert status code when non-error response is received
            self.assertEqual(response.status_code, 302)

    def test_location_restricted_user_can_send_scheduled_report(self):
        with self._get_web_user_with_permissions_added() as user:
            config = self.create_report_config(self.domain, user._id)
            rn = self.create_report_notification([config], owner_id=user._id)
            url = reverse('send_test_scheduled_report', args=(self.domain, rn._id))
            response = self.client.post(url)
            # Assert status code when forbidden error is not received
            self.assertNotEqual(response.status_code, 403)
            # Assert status code when forbidden error is not received
            self.assertEqual(response.status_code, 302)

    def test_location_restricted_user_can_delete_saved_report(self):
        with self._get_web_user_with_permissions_added() as user:
            config = self.create_report_config(self.domain, user._id)
            url = reverse('delete_report_config', args=(self.domain, config._id))
            response = self.client.delete(url)
            # Assert status code when forbidden error is not received
            self.assertNotEqual(response.status_code, 403)
            # Assert status code when forbidden error is not received
            self.assertEqual(response.status_code, 200)

    def _get_web_user_with_permissions_added(self):
        permissions = {
            'download_reports': True,
            'view_reports': True,
        }
        web_user = get_web_user(
            self.domain,
            self.user_location,
            permissions,
            self.client,
        )
        return web_user

    def create_report_config(self, domain, owner_id, **kwargs):
        rc = ReportConfig(domain=domain, owner_id=owner_id, **kwargs)
        rc.save()
        self.addCleanup(rc.delete)
        return rc

    def create_report_notification(self, configs, owner_id):
        domain = configs[0].domain
        config_ids = [c._id for c in configs]
        rn = ReportNotification(
            domain=domain,
            config_ids=config_ids,
            owner_id=owner_id,
            interval='daily',
        )
        rn.save()
        self.addCleanup(rn.delete)
        return rn


@contextmanager
def get_web_user(domain, location, permissions, client):
    username = 'admin@example.com'
    password = '************'
    role = UserRole.create(
        domain,
        'edit-data',
        permissions=HqPermissions(**permissions),
    )

    web_user = WebUser.create(
        domain,
        username,
        password,
        created_by=None,
        created_via=None,
        role_id=role.get_id,
    )
    web_user.set_location(domain, location)
    manager.index_refresh(user_adapter.index_name)
    client.login(username=username, password=password)
    try:
        yield web_user
    finally:
        web_user.delete(domain, deleted_by=None)
        role.delete()
