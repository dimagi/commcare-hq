from uuid import uuid4

from django.core import management

from couchdbkit.ext.django.loading import get_db

from ..models import NavigationEventAudit
from ..utils.export import navigation_events_by_user
from .testutils import AuditcareTest

USERNAME = "gdpr_user1"


class TestGDPRScrubUserAuditcare(AuditcareTest):

    def setUp(self):
        NavigationEventAudit(user=USERNAME, path="/fake/path/0").save()
        NavigationEventAudit(user=USERNAME, path="/fake/path/1").save()
        NavigationEventAudit(user=USERNAME, path="/fake/path/2").save()
        self.couch_ids = [
            save_couch_doc("NavigationEventAudit", USERNAME, path="/fake/path/3"),
            save_couch_doc("AccessAudit", USERNAME, ip_address="123.45.67.89"),
        ]

    def tearDown(self):
        db = get_db("auditcare")
        for doc_id in self.couch_ids:
            db.delete_doc(doc_id)

    def test_update_username_no_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", "nonexistent_user")
        self.assertEqual(navigation_events_by_user("Redacted User (GDPR)").count(), 0)
        self.assertEqual(navigation_events_by_user(USERNAME).count(), 5)

    def test_update_username_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", USERNAME)
        self.assertEqual(navigation_events_by_user("Redacted User (GDPR)").count(), 5)
        self.assertEqual(navigation_events_by_user(USERNAME).count(), 0)


def save_couch_doc(doc_type, user, **doc):
    db = get_db("auditcare")
    doc.update(doc_type=doc_type, user=user, _id=uuid4().hex, base_type="AuditEvent")
    return db.save_doc(doc)["id"]
