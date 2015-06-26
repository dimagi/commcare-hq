from datetime import datetime
import uuid
from django.test import TestCase
from django.test.utils import override_settings
from casexml.apps.phone.exceptions import IncompatibleSyncLogType
from casexml.apps.phone.models import User, SyncLog, SimplifiedSyncLog
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from casexml.apps.phone.tests.utils import synclog_from_restore_payload
from corehq.apps.domain.models import Domain
from corehq.toggles import OWNERSHIP_CLEANLINESS_RESTORE


@override_settings(TESTS_SHOULD_USE_CLEAN_RESTORE=None)
class TestChangingSyncMode(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = uuid.uuid4().hex
        cls.project = Domain(name=cls.domain)
        cls.user_id = uuid.uuid4().hex
        cls.user = User(user_id=cls.user_id, username=uuid.uuid4().hex,
                        password="changeme", date_joined=datetime(2014, 6, 6))

    def test_old_then_new_sync(self):
        restore_config = RestoreConfig(self.project, user=self.user)
        sync_log = synclog_from_restore_payload(restore_config.get_payload().as_string())
        self.assertEqual(SyncLog, type(sync_log))
        OWNERSHIP_CLEANLINESS_RESTORE.set(self.domain, enabled=True, namespace='domain')
        restore_config = RestoreConfig(self.project, user=self.user,
                                       params=RestoreParams(sync_log_id=sync_log._id))
        with self.assertRaises(IncompatibleSyncLogType):
            restore_config.get_payload()
        OWNERSHIP_CLEANLINESS_RESTORE.set(self.domain, enabled=False, namespace='domain')

    def test_new_then_old_sync(self):
        OWNERSHIP_CLEANLINESS_RESTORE.set(self.domain, enabled=True, namespace='domain')
        restore_config = RestoreConfig(self.project, user=self.user)
        sync_log = synclog_from_restore_payload(restore_config.get_payload().as_string())
        self.assertEqual(SimplifiedSyncLog, type(sync_log))
        OWNERSHIP_CLEANLINESS_RESTORE.set(self.domain, enabled=False, namespace='domain')
        restore_config = RestoreConfig(self.project, user=self.user,
                                       params=RestoreParams(sync_log_id=sync_log._id))
        with self.assertRaises(IncompatibleSyncLogType):
            restore_config.get_payload()
