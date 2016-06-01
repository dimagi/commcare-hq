from django.test import TestCase
from django.test.utils import override_settings
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.models import User, get_properly_wrapped_sync_log
from datetime import datetime
from casexml.apps.phone.checksum import EMPTY_HASH, CaseStateHash
from casexml.apps.case.xml import V2
from casexml.apps.case.tests.util import delete_all_sync_logs, delete_all_xforms, delete_all_cases
from casexml.apps.phone.exceptions import BadStateException
from casexml.apps.phone.tests.utils import generate_restore_response, \
    get_exactly_one_wrapped_sync_log, generate_restore_payload
from corehq.apps.domain.models import Domain
from corehq.form_processor.tests import run_with_all_backends


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class StateHashTest(TestCase):
    
    def setUp(self):
        delete_all_cases()
        delete_all_xforms()
        delete_all_sync_logs()
        self.project = Domain(name='state-hash-tests-project')
        self.user = User(user_id="state_hash", username="state_hash",
                         password="changeme", date_joined=datetime(2011, 6, 9))

        # this creates the initial blank sync token in the database
        generate_restore_payload(self.project, self.user)
        self.sync_log = get_exactly_one_wrapped_sync_log()

    @run_with_all_backends
    def testEmpty(self):
        empty_hash = CaseStateHash(EMPTY_HASH)
        wrong_hash = CaseStateHash("thisisntright")
        self.assertEqual(empty_hash, self.sync_log.get_state_hash())
        response = generate_restore_response(self.project, self.user, self.sync_log.get_id, version=V2)
        self.assertEqual(200, response.status_code)
        
        try:
            generate_restore_payload(
                self.project, self.user, self.sync_log.get_id,
                version=V2, state_hash=str(wrong_hash)
            )
            self.fail("Call to generate a payload with a bad hash should fail!")
        except BadStateException, e:
            self.assertEqual(empty_hash, e.server_hash)
            self.assertEqual(wrong_hash, e.phone_hash)
            self.assertEqual(0, len(e.case_ids))

        response = generate_restore_response(self.project, self.user, self.sync_log.get_id, version=V2,
                                             state_hash=str(wrong_hash))
        self.assertEqual(412, response.status_code)

    @run_with_all_backends
    def testMismatch(self):
        self.assertEqual(CaseStateHash(EMPTY_HASH), self.sync_log.get_state_hash())
        
        c1 = CaseBlock(case_id="abc123", create=True, 
                       owner_id=self.user.user_id).as_xml()
        c2 = CaseBlock(case_id="123abc", create=True, 
                       owner_id=self.user.user_id).as_xml()
        post_case_blocks([c1, c2],
                         form_extras={"last_sync_token": self.sync_log.get_id})
        
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log.get_id)
        real_hash = CaseStateHash("409c5c597fa2c2a693b769f0d2ad432b")
        bad_hash = CaseStateHash("thisisntright")
        self.assertEqual(real_hash, self.sync_log.get_state_hash())
        generate_restore_payload(
            self.project, self.user, self.sync_log.get_id,
            version=V2, state_hash=str(real_hash)
        )
        
        try:
            generate_restore_payload(self.project, self.user, self.sync_log.get_id,
                                     version=V2, state_hash=str(bad_hash))
            self.fail("Call to generate a payload with a bad hash should fail!")
        except BadStateException, e:
            self.assertEqual(real_hash, e.server_hash)
            self.assertEqual(bad_hash, e.phone_hash)
            self.assertEqual(2, len(e.case_ids))
            self.assertTrue("abc123" in e.case_ids)
            self.assertTrue("123abc" in e.case_ids)
