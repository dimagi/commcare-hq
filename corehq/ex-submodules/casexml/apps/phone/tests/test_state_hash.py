from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from django.test.utils import override_settings
from casexml.apps.case.mock import CaseBlock
from casexml.apps.phone.checksum import EMPTY_HASH, CaseStateHash
from casexml.apps.case.xml import V1
from casexml.apps.case.tests.util import delete_all_sync_logs, delete_all_xforms, delete_all_cases
from casexml.apps.phone.exceptions import BadStateException
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.phone.utils import MockDevice
from corehq.apps.domain.models import Domain
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.form_processor.tests.utils import use_sql_backend


class StateHashTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(StateHashTest, cls).setUpClass()
        delete_all_users()
        cls.project = Domain(name='state-hash-tests-project')
        cls.project.save()
        cls.user = create_restore_user(domain=cls.project.name)

    def setUp(self):
        super(StateHashTest, self).setUp()
        delete_all_cases()
        delete_all_xforms()
        delete_all_sync_logs()

        # this creates the initial blank sync token in the database
        self.device = MockDevice(self.project, self.user)
        self.device.sync(version=V1)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        delete_all_users()
        super(StateHashTest, cls).tearDownClass()

    def testEmpty(self):
        empty_hash = CaseStateHash(EMPTY_HASH)
        wrong_hash = CaseStateHash("thisisntright")
        self.assertEqual(empty_hash, self.device.last_sync.log.get_state_hash())
        response = self.device.get_restore_config().get_response()
        self.assertEqual(200, response.status_code)

        config = self.device.get_restore_config(state_hash=str(wrong_hash))
        try:
            config.get_payload()
        except BadStateException as e:
            self.assertEqual(empty_hash, e.server_hash)
            self.assertEqual(wrong_hash, e.phone_hash)
            self.assertEqual(0, len(e.case_ids))
        else:
            self.fail("Call to generate a payload with a bad hash should fail!")

        self.assertEqual(412, config.get_response().status_code)

    def testMismatch(self):
        sync = self.device.last_sync
        self.assertEqual(CaseStateHash(EMPTY_HASH), sync.log.get_state_hash())

        c1 = CaseBlock(case_id="abc123", create=True, owner_id=self.user.user_id)
        c2 = CaseBlock(case_id="123abc", create=True, owner_id=self.user.user_id)
        self.device.post_changes([c1, c2])

        real_hash = CaseStateHash("409c5c597fa2c2a693b769f0d2ad432b")
        bad_hash = CaseStateHash("thisisntright")
        self.assertEqual(real_hash, sync.get_log().get_state_hash())
        self.device.sync(state_hash=str(real_hash))

        self.device.last_sync = sync
        try:
            self.device.sync(state_hash=str(bad_hash))
        except BadStateException as e:
            self.assertEqual(real_hash, e.server_hash)
            self.assertEqual(bad_hash, e.phone_hash)
            self.assertEqual(set(e.case_ids), {"abc123", "123abc"})
        else:
            self.fail("Call to generate a payload with a bad hash should fail!")


@use_sql_backend
class StateHashTestSQL(StateHashTest):
    pass
