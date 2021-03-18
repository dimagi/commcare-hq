from django.core import management

from ..models import NavigationEventAudit
from ..utils.export import navigation_events_by_user
from .testutils import AuditcareTest

USERNAME = "gdpr_user1"


class TestGDPRScrubUserAuditcare(AuditcareTest):

    def setUp(self):
        NavigationEventAudit(user=USERNAME, path="/fake/path/0").save()
        NavigationEventAudit(user=USERNAME, path="/fake/path/1").save()
        NavigationEventAudit(user=USERNAME, path="/fake/path/2").save()

    def test_update_username_no_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", "nonexistent_user")
        self.assertEqual(navigation_events_by_user("Redacted User (GDPR)").count(), 0)
        self.assertEqual(navigation_events_by_user(USERNAME).count(), 3)

    def test_update_username_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", USERNAME)
        self.assertEqual(navigation_events_by_user("Redacted User (GDPR)").count(), 3)
        self.assertEqual(navigation_events_by_user(USERNAME).count(), 0)
