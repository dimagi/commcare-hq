from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from django.core import management
from auditcare.utils.export import get_auditcare_docs_by_username
from auditcare.models import NavigationEventAudit
from auditcare.management.commands.gdpr_scrub_user_auditcare import Command
from dimagi.utils.couch.database import iter_bulk_delete


class TestGDPRScrubUserAuditcare(TestCase):

    def setUp(self):
        NavigationEventAudit(user="test_user1", request_path="/fake/path/0").save()
        NavigationEventAudit(user="test_user1", request_path="/fake/path/1").save()
        NavigationEventAudit(user="test_user1", request_path="/fake/path/2").save()
        self.returned_docs = get_auditcare_docs_by_username("test_user1")

    def tearDown(self):
        all_auditcare_ids = list(set([result["id"] for result in NavigationEventAudit.get_db().view(
            "auditcare/urlpath_by_user_date",
            reduce=False,
        ).all()]))
        iter_bulk_delete(NavigationEventAudit.get_db(), all_auditcare_ids)

    def test_get_docs_by_existing_user(self):
        auditcare_returned_docs = get_auditcare_docs_by_username("test_user1")
        self.assertEqual(len(auditcare_returned_docs), 3)
        self.assertEqual(auditcare_returned_docs[0].request_path, "/fake/path/2")
        self.assertEqual(auditcare_returned_docs[1].request_path, "/fake/path/1")
        self.assertEqual(auditcare_returned_docs[2].request_path, "/fake/path/0")

    def test_get_docs_by_nonexistent_user(self):
        username = "nonexistent_user"
        auditcare_returned_docs = get_auditcare_docs_by_username(username)
        self.assertEqual(len(auditcare_returned_docs), 0)

    def test_update_username_no_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", "nonexistent_user")
        redacted_username_docs = get_auditcare_docs_by_username("Redacted User (GDPR)")
        self.assertEqual(len(redacted_username_docs), 0)
        orig_username_docs = get_auditcare_docs_by_username("test_user1")
        self.assertEqual(len(orig_username_docs), 3)

    def test_update_username_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", "test_user1")
        orig_username_docs = get_auditcare_docs_by_username("test_user1")
        self.assertEqual(len(orig_username_docs), 0)
        redacted_username_docs = get_auditcare_docs_by_username("Redacted User (GDPR)")
        self.assertEqual(len(redacted_username_docs), 3)
