from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
import time
from django.test import Client
from auditcare.inspect import history_for_doc
from auditcare.utils import _thread_locals
from django.contrib.auth.models import User
from auditcare.models import AuditEvent, ModelActionAudit
from auditcare.tests.testutils import delete_all
from django.test import TestCase
from mock import mock
from corehq.apps.users.models import CommCareUser

from auditcare.management.commands.gdpr_scrub_user_auditcare import Command
from auditcare.utils.export import get_auditcare_docs_by_username
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from auditcare.models import NavigationEventAudit
from corehq.apps.users.dbaccessors.all_commcare_users import get_user_docs_by_username

from collections import namedtuple

from corehq.apps.users.models import CommCareUser
from corehq.apps.es import UserES
from corehq.util.quickcache import quickcache
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.couch.database import iter_docs, iter_bulk_delete
from six.moves import map



class TestGDPRScrubUserAuditcare(TestCase):

    def setUp(self):
        # delete_all_auditcare_entries()
        NavigationEventAudit(user='test_user').save()
        pass

    def tearDown(self):
        delete_all_auditcare_entries()
        pass

    def test_get_docs_by_user(self):
        pass
        username = "test_user"
        auditcare_returned_docs = get_auditcare_docs_by_username(username)

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
