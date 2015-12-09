from corehq.apps.reports.util import create_export_filter
from corehq.apps.users.models import CommCareUser
from django.test import TestCase
from mock import Mock


DOMAIN = 'test_domain'


class ReportUtilTests(TestCase):

    def setUp(self):
        self.user = CommCareUser.create(DOMAIN, 'user1', '***')
        self.request = Mock()
        self.request.method = 'POST'
        self.request.POST = {}
        self.request.project.commtrack_enabled = False
        self.request.couch_user = self.user.user_id

    def tearDown(self):
        self.user.delete()

    def test_create_export_form_filter(self):
        filter_ = create_export_filter(self.request, DOMAIN, export_type='form')
        self.assertEqual(
            filter_.dumps(),
            '[{"function": "corehq.apps.reports.util.app_export_filter", "kwargs": {"app_id": null}},'
            ' {"function": "corehq.apps.reports.util.datespan_export_filter", "kwargs": {"datespan": null}},'
            ' {"function": "corehq.apps.reports.util.users_filter", "kwargs": {"users": ["' +
            self.user.user_id + '"]}}]')

    def test_create_export_case_filter(self):
        filter_ = create_export_filter(self.request, DOMAIN, export_type='case')
        self.assertEqual(
            filter_.dumps(),
            '[{"function": "corehq.apps.reports.util.case_users_filter", "kwargs": {"users": ["' +
            self.user.user_id + '"], "groups": []}}]')
