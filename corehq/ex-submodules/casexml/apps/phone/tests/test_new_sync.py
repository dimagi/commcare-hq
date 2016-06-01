from datetime import datetime
import uuid
from django.test import TestCase, SimpleTestCase
from jsonobject import JsonObject
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.phone.exceptions import IncompatibleSyncLogType
from casexml.apps.phone.models import User, SyncLog, SimplifiedSyncLog, LOG_FORMAT_SIMPLIFIED, LOG_FORMAT_LEGACY, \
    CaseState
from casexml.apps.phone.restore import RestoreConfig
from casexml.apps.phone.tests.utils import synclog_from_restore_payload
from corehq.apps.domain.models import Domain
from corehq.form_processor.tests import run_with_all_backends
from corehq.toggles import LEGACY_SYNC_SUPPORT
from corehq.util.global_request.api import set_request


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
        sync_log = SyncLog(
            cases_on_phone=[
                CaseState(
                    case_id='bran',
                    indices=[CommCareCaseIndex(identifier='legs', referenced_id='hodor')],
                ),
            ],
            dependent_cases_on_phone=[CaseState(case_id='hodor')]
        )
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        self.assertTrue('bran' in migrated.case_ids_on_phone)
        self.assertTrue('hodor' in migrated.case_ids_on_phone)
        self.assertTrue('hodor' in migrated.dependent_case_ids_on_phone)

    def test_indices(self):
        parents = ['catelyn', 'ned', 'cersei', 'jaimie']
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
                ]),
                CaseState(case_id='myrcella', indices=[
                    CommCareCaseIndex(**args) for args in index_structure['myrcella']
                ])
            ],
            dependent_cases_on_phone=[
                CaseState(case_id=parent) for parent in parents
            ]
        )
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        for case_id, indices in index_structure.items():
            self.assertTrue(case_id in migrated.index_tree.indices)
            for index in indices:
                self.assertEqual(index['referenced_id'],
                                 migrated.index_tree.indices[case_id][index['identifier']])
        for parent in parents:
            self.assertTrue(parent in migrated.case_ids_on_phone)
            self.assertTrue(parent in migrated.dependent_case_ids_on_phone)

    def test_purge_on_migrate(self):
        sync_log = SyncLog(
            cases_on_phone=[
                CaseState(case_id='robert'),
                CaseState(case_id='cersei'),
            ],
            dependent_cases_on_phone=[
                CaseState(case_id='gendry')
            ]
        )
        migrated = SimplifiedSyncLog.from_other_format(sync_log)
        self.assertTrue('gendry' not in migrated.case_ids_on_phone)
        self.assertEqual(sync_log.get_state_hash(), migrated.get_state_hash())

    def test_migrate_backwards(self):
        with self.assertRaises(IncompatibleSyncLogType):
            SyncLog.from_other_format(SimplifiedSyncLog())


class TestNewSyncSpecifics(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = uuid.uuid4().hex
        cls.project = Domain(name=cls.domain)
        cls.user_id = uuid.uuid4().hex
        cls.user = User(user_id=cls.user_id, username=uuid.uuid4().hex,
                        password="changeme", date_joined=datetime(2014, 6, 6))

    @run_with_all_backends
    def test_legacy_support_toggle(self):
        restore_config = RestoreConfig(self.project, user=self.user)
        factory = CaseFactory(domain=self.project.name, case_defaults={'owner_id': self.user_id})
        # create a parent and child case (with index) from one user
        parent_id, child_id = [uuid.uuid4().hex for i in range(2)]
        factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship='child',
                    related_type='parent',
                )],
            )
        ])
        restore_payload = restore_config.get_payload().as_string()
        self.assertTrue(child_id in restore_payload)
        self.assertTrue(parent_id in restore_payload)
        sync_log = synclog_from_restore_payload(restore_payload)
        self.assertEqual(SimplifiedSyncLog, type(sync_log))
        # make both cases irrelevant by changing the owner ids
        factory.create_or_update_cases([
            CaseStructure(case_id=parent_id, attrs={'owner_id': 'different'}),
            CaseStructure(case_id=child_id, attrs={'owner_id': 'different'}),
        ], form_extras={'last_sync_token': sync_log._id})

        # doing it again should fail since they are no longer relevant

        # todo: add this back in when we add the assertion back. see SimplifiedSyncLog.prune_case
        # with self.assertRaises(SimplifiedSyncAssertionError):
        #     factory.create_or_update_cases([
        #         CaseStructure(case_id=child_id, attrs={'owner_id': 'different'}),
        #         CaseStructure(case_id=parent_id, attrs={'owner_id': 'different'}),
        #     ], form_extras={'last_sync_token': sync_log._id})

        # enabling the toggle should prevent the failure the second time
        # though we also need to hackily set the request object in the threadlocals
        LEGACY_SYNC_SUPPORT.set(self.domain, True, namespace='domain')
        request = JsonObject(domain=self.domain, path='testsubmit')
        set_request(request)
        factory.create_or_update_cases([
            CaseStructure(case_id=child_id, attrs={'owner_id': 'different'}),
            CaseStructure(case_id=parent_id, attrs={'owner_id': 'different'}),
        ], form_extras={'last_sync_token': sync_log._id})
