from casexml.apps.phone.tests.test_ota_restore import OtaRestoreTest
from casexml.apps.phone.tests.test_sync_mode import SyncTokenUpdateTest, USERNAME, MultiUserSyncTest
from corehq.toggles import BATCHED_RESTORE
from toggle.models import Toggle


"""
Run the same tests but the BATCH_RESTORE toggle enabled
"""


class EnableBatchToggleMixin(object):
    @classmethod
    def setUpClass(cls):
        cls.toggle = Toggle(slug=BATCHED_RESTORE.slug, enabled_users=[USERNAME])
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