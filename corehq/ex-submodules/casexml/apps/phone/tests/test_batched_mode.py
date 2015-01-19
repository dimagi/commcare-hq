from mock import patch
from casexml.apps.case.tests.util import assert_user_has_cases, assert_user_doesnt_have_cases
from casexml.apps.phone.tests.test_ota_restore import OtaRestoreTest
from casexml.apps.phone.tests.test_sync_mode import (
    SyncTokenUpdateTest, USERNAME, USER_ID,
    MultiUserSyncTest, OTHER_USERNAME,
    SyncBaseTest)
from corehq.toggles import BATCHED_RESTORE
from toggle.models import Toggle


"""
Run the same tests but the BATCH_RESTORE toggle enabled
"""


class EnableBatchToggleMixin(object):
    @classmethod
    def setUpClass(cls):
        cls.toggle = Toggle(slug=BATCHED_RESTORE.slug, enabled_users=[USERNAME, OTHER_USERNAME])
        cls.toggle.save()

    @classmethod
    def tearDownClass(cls):
        cls.toggle.delete()


class SyncTokenUpdateTestBatched(EnableBatchToggleMixin, SyncTokenUpdateTest):
    pass


class MultiUserSyncTestBatched(EnableBatchToggleMixin, MultiUserSyncTest):
    pass


class OtaRestoreTestBatched(EnableBatchToggleMixin, OtaRestoreTest):
    pass


@patch('casexml.apps.phone.caselogic.BatchedCaseSyncOperation.chunk_size', new=3)
class BatchRestoreTests(EnableBatchToggleMixin, SyncBaseTest):

    def test_multiple_batches_restore(self):
        case_ids = ["case_{}".format(i) for i in range(10)]
        self._createCaseStubs(case_ids, owner_id=USER_ID)

        restore_config, _ = assert_user_has_cases(self, self.user, case_ids)
        self.assertEqual(restore_config.num_batches, 4)

    def test_multiple_batches_sync(self):
        case_ids = ["case_{}".format(i) for i in range(10)]
        self._createCaseStubs(case_ids, owner_id=USER_ID)

        restore_config, _ = assert_user_doesnt_have_cases(self, self.user, case_ids,
                                                          restore_id=self.sync_log.get_id)
        # 4 batches to fetch cases + 1 batch for cases left on phone
        self.assertEqual(restore_config.num_batches, 5)
