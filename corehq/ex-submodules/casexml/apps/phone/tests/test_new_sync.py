from datetime import datetime
import uuid
from django.test import TestCase, SimpleTestCase
from django.test.utils import override_settings
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.phone.exceptions import IncompatibleSyncLogType
from casexml.apps.phone.models import User, SyncLog, SimplifiedSyncLog, LOG_FORMAT_SIMPLIFIED, LOG_FORMAT_LEGACY, \
    CaseState
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings
from casexml.apps.phone.tests.utils import synclog_from_restore_payload
from corehq.apps.domain.models import Domain
from corehq.toggles import OWNERSHIP_CLEANLINESS_RESTORE


class TestSyncLogMigration(SimpleTestCase):

    def test_shared_properties_migrate(self):
        attrs = {
            'date': datetime.utcnow(),
            'user_id': 'ned',
            'previous_log_id': 'previous-log',
            'duration': 10,
            'owner_ids': ['arya', 'sansa'],
        }
        sync_log = SyncLog(**attrs)
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        for k, v in attrs.items():
            self.assertEqual(v, getattr(migrated, k))

    def test_log_format_chages(self):
        sync_log = SyncLog()
        self.assertEqual(LOG_FORMAT_LEGACY, sync_log.log_format)
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        self.assertEqual(LOG_FORMAT_SIMPLIFIED, migrated.log_format)

    def test_properties_deleted(self):
        sync_log = SyncLog(
            cases_on_phone=[CaseState(case_id='nymeria')],
            dependent_cases_on_phone=[CaseState(case_id='lady')],
        )
        self.assertTrue(hasattr(sync_log, 'cases_on_phone'))
        self.assertTrue(hasattr(sync_log, 'dependent_cases_on_phone'))
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        self.assertFalse(hasattr(migrated, 'cases_on_phone'))
        self.assertFalse(hasattr(migrated, 'dependent_cases_on_phone'))

    def test_cases_on_phone(self):
        case_ids = ['nymeria', 'lady']
        sync_log = SyncLog(
            cases_on_phone=[CaseState(case_id=case_id) for case_id in case_ids],
        )
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        for case_id in case_ids:
            self.assertTrue(case_id in migrated.case_ids_on_phone)
            self.assertFalse(case_id in migrated.dependent_case_ids_on_phone)

    def test_dependent_cases_on_phone(self):
        case_ids = ['summer', 'ghost']
        sync_log = SyncLog(
            dependent_cases_on_phone=[CaseState(case_id=case_id) for case_id in case_ids],
        )
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        for case_id in case_ids:
            self.assertTrue(case_id in migrated.case_ids_on_phone)
            self.assertTrue(case_id in migrated.dependent_case_ids_on_phone)

    def test_indices(self):
        index_structure = {
            'bran': [
                {'identifier': 'mom', 'referenced_id': 'catelyn'},
                {'identifier': 'dad', 'referenced_id': 'ned'},
            ],
            'myrcella': [
                {'identifier': 'mom', 'referenced_id': 'cersei'},
                {'identifier': 'dad', 'referenced_id': 'jaimie'},
            ]
        }
        sync_log = SyncLog(
            cases_on_phone=[
                CaseState(case_id='bran', indices=[
                    CommCareCaseIndex(**args) for args in index_structure['bran']
                ])
            ],
            dependent_cases_on_phone=[
                CaseState(case_id='myrcella', indices=[
                    CommCareCaseIndex(**args) for args in index_structure['myrcella']
                ])
            ]
        )
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        for case_id, indices in index_structure.items():
            self.assertTrue(case_id in migrated.index_tree.indices)
            for index in indices:
                self.assertEqual(index['referenced_id'],
                                 migrated.index_tree.indices[case_id][index['identifier']])

    def test_migrate_backwards(self):
        with self.assertRaises(IncompatibleSyncLogType):
            SyncLog.from_other_format(SimplifiedSyncLog())


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
        case = CaseFactory(domain=self.project.name, case_defaults={'owner_id': self.user_id}).create_case()
        restore_payload = restore_config.get_payload().as_string()
        self.assertTrue(case._id in restore_payload)
        sync_log = synclog_from_restore_payload(restore_payload)
        self.assertEqual(SyncLog, type(sync_log))
        restore_config = RestoreConfig(self.project, user=self.user,
                                       params=RestoreParams(sync_log_id=sync_log._id))
        original_payload_back = restore_config.get_payload().as_string()
        self.assertFalse(case._id in original_payload_back)
        self.assertEqual(SyncLog, type(synclog_from_restore_payload(original_payload_back)))

        OWNERSHIP_CLEANLINESS_RESTORE.set(self.domain, enabled=True, namespace='domain')
        restore_config = RestoreConfig(self.project, user=self.user,
                                       params=RestoreParams(sync_log_id=sync_log._id),
                                       cache_settings=RestoreCacheSettings(overwrite_cache=True))
        migrated_payload_back = restore_config.get_payload().as_string()
        self.assertFalse(case._id in migrated_payload_back)
        self.assertEqual(SimplifiedSyncLog, type(synclog_from_restore_payload(migrated_payload_back)))
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
