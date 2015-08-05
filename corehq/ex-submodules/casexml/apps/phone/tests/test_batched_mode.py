from django.test.utils import override_settings
from mock import patch
from casexml.apps.case.tests.util import assert_user_has_cases, assert_user_doesnt_have_cases
from casexml.apps.phone.tests.test_sync_mode import USER_ID, SyncBaseTest


@patch('casexml.apps.phone.data_providers.case.batched.BatchedCaseSyncOperation.chunk_size', new=3)
@override_settings(TESTS_SHOULD_USE_CLEAN_RESTORE=False)
class BatchRestoreTests(SyncBaseTest):

    def test_multiple_batches_restore(self):
        case_ids = ["case_{}".format(i) for i in range(10)]
        self._createCaseStubs(case_ids, owner_id=USER_ID)

        restore_config, _ = assert_user_has_cases(self, self.user, case_ids)
        self.assertEqual(restore_config.restore_state.provider_log['num_case_batches'], 4)

    def test_multiple_batches_sync(self):
        case_ids = ["case_{}".format(i) for i in range(10)]
        self._createCaseStubs(case_ids, owner_id=USER_ID)

        restore_config, _ = assert_user_doesnt_have_cases(self, self.user, case_ids,
                                                          restore_id=self.sync_log.get_id)
        # 4 batches to fetch cases + 1 batch for cases left on phone
        self.assertEqual(restore_config.restore_state.provider_log['num_case_batches'], 5)
