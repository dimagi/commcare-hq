from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from auditcare.utils.export import get_auditcare_docs_by_username
from auditcare.models import NavigationEventAudit
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.couch.database import iter_bulk_delete
import uuid


class TestGDPRScrubUserAuditcare(TestCase):

    def setUp(self):
        delete_all_auditcare_entries()
        NavigationEventAudit(user='test_user1', request_path="/fake/path/1").save()
        NavigationEventAudit(user='test_user1', request_path="/fake/path/2").save()
        NavigationEventAudit(user='test_user1', request_path="/fake/path/3").save()
        pass

    def tearDown(self):
        delete_all_auditcare_entries()
        pass

    def test_get_docs_by_user(self):
        username = "test_user1"
        auditcare_returned_docs = get_auditcare_docs_by_username(username)
        print("auditcare_returned_docs: {}".format(auditcare_returned_docs))
        self.assertEqual(len(auditcare_returned_docs), 3)


@unit_testing_only
def delete_all_auditcare_entries():
    all_auditcare_ids = list(set([result['id'] for result in NavigationEventAudit.get_db().view(
        'auditcare/urlpath_by_user_date',
        reduce=False,
    ).all()]))

    iter_bulk_delete(NavigationEventAudit.get_db(), all_auditcare_ids)

#     #
#     # # @mock.patch('auditcare.management.commands.gdpr_scrub_user_auditcare.get_docs_by_user', return_value=[])
#     # # def test_handle_no_docs_returned(self, _):
#     # #     Command().handle(username="fake_username")
#     # #     self.assertEqual(len(self.foo_log_messages['info']), 5)
#     # #     for info_message in self.foo_log_messages['info']:
#     # #         self.assertIn('fromble', info_message)
#     #
#     # # @mock.patch('auditcare.management.commands.gdpr_scrub_user_auditcare.get_docs_by_user', return_value=[1, 2, 3])
#     # # def test_handle_multiple_docs_returned(self, _):
#     # #     Command().handle(username="fake_username")
