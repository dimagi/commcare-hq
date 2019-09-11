from django.test import TestCase
from django.core import management
from auditcare.utils.export import navigation_event_ids_by_user
from auditcare.models import NavigationEventAudit
from dimagi.utils.couch.database import iter_bulk_delete


class TestGDPRScrubUserAuditcare(TestCase):

    def setUp(self):
        NavigationEventAudit(user="test_user1", request_path="/fake/path/0").save()
        NavigationEventAudit(user="test_user1", request_path="/fake/path/1").save()
        NavigationEventAudit(user="test_user1", request_path="/fake/path/2").save()

    def tearDown(self):
        all_auditcare_ids = list(set([result["id"] for result in NavigationEventAudit.get_db().view(
            "auditcare/urlpath_by_user_date",
            reduce=False,
        ).all()]))
        iter_bulk_delete(NavigationEventAudit.get_db(), all_auditcare_ids)

    def test_update_username_no_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", "nonexistent_user")
        num_redacted_users = navigation_event_ids_by_user("Redacted User (GDPR)")
        self.assertEqual(len(num_redacted_users), 0)
        num_original_users = navigation_event_ids_by_user("test_user1")
        self.assertEqual(len(num_original_users), 3)

    def test_update_username_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", "test_user1")
        num_redacted_users = navigation_event_ids_by_user("Redacted User (GDPR)")
        self.assertEqual(len(num_redacted_users), 3)
        num_original_users = navigation_event_ids_by_user("test_user1")
        self.assertEqual(len(num_original_users), 0)
