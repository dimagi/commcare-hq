import uuid

from django.test import TestCase

from mock import Mock

from corehq.apps.users.models import CommCareUser
from corehq.util.test_utils import generate_cases
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.middleware import ICDSAuditMiddleware
from custom.icds_reports.models import ICDSAuditEntryRecord


class TestICDSAuditData(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestICDSAuditData, cls).setUpClass()
        cls.user = CommCareUser.create(DASHBOARD_DOMAIN, 'test', '123')

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        super(TestICDSAuditData, cls).tearDownClass()

    def tearDown(self):
        ICDSAuditEntryRecord.objects.all().delete()
        super(TestICDSAuditData, self).tearDown()

    def _test_request(self, domain, path, response_code=200, expected_event=True):
        request = Mock()
        request.path = path
        request.domain = domain
        request.GET = {}
        request.POST = {}
        request.META = {
            'HTTP_X_FORWARDED_FOR': '10.99.100.1'
        }
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.username = 'test'
        request.couch_user = self.user
        request.session = Mock()
        request.session.session_key = uuid.uuid4().hex

        response = Mock()
        response.status_code = response_code
        ICDSAuditMiddleware().process_response(request, response)
        events = list(ICDSAuditEntryRecord.objects.all())
        event = events[0] if events else None

        if expected_event:
            self.assertIsNotNone(event)
            self.assertEqual(event.url, path)
            self.assertEqual(event.response_code, response_code)
        else:
            self.assertIsNone(event)


@generate_cases([
    (DASHBOARD_DOMAIN, '/a/{domain}/login/', 200, True),
    (DASHBOARD_DOMAIN, '/a/{domain}/icds_download_pdf/', 401, True),
    ('other', '/a/{domain}/icds_download_pdf/', 200, False),
], TestICDSAuditData)
def test_audit_events(self, domain, path, response_code, expected_event):
    path = path.format(domain=domain)
    self._test_request(domain, path, response_code, expected_event)
