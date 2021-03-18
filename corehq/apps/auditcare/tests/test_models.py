from django.test import RequestFactory
from testil import Config

from corehq.apps.auditcare.models import NavigationEventAudit

from .test_middleware import make_view
from .testutils import AuditcareTest


class TestNavigationEventAudit(AuditcareTest):

    def setUp(self):
        self.request = RequestFactory().get("/path", {"key": "value"})
        self.request.session = Config(session_key="abc")

    def test_audit_view_should_not_save(self):
        view = make_view()
        event = NavigationEventAudit.audit_view(self.request, "username", view, {})
        self.assertIsNone(event.id)
