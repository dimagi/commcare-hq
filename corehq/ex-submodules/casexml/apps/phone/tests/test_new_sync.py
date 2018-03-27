from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import uuid
from django.test import TestCase, SimpleTestCase
from jsonobject import JsonObject
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.phone.const import CLEAN_OWNERS, LIVEQUERY
from casexml.apps.phone.exceptions import IncompatibleSyncLogType, RestoreException
from casexml.apps.phone.models import (
    CaseState,
    LOG_FORMAT_LEGACY,
    LOG_FORMAT_LIVEQUERY,
    LOG_FORMAT_SIMPLIFIED,
    SimplifiedSyncLog,
    SyncLog,
)
from casexml.apps.phone.restore import RestoreConfig
from casexml.apps.phone.tests.utils import (
    create_restore_user,
    deprecated_synclog_from_restore_payload,
)
from casexml.apps.phone.utils import MockDevice
from corehq.apps.domain.models import Domain
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.toggles import LEGACY_SYNC_SUPPORT
from corehq.util.global_request.api import set_request
from six.moves import range


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

    def test_livequery_to_legacy(self):
        sync_log = SimplifiedSyncLog(log_format=LOG_FORMAT_LIVEQUERY)
        with self.assertRaises(IncompatibleSyncLogType):
            SyncLog.from_other_format(sync_log)

    def test_livequery_to_simplified(self):
        sync_log = SimplifiedSyncLog(log_format=LOG_FORMAT_LIVEQUERY)
        with self.assertRaises(IncompatibleSyncLogType):
            SimplifiedSyncLog.from_other_format(sync_log)


class TestLiveQuery(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLiveQuery, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.project = Domain(name=cls.domain)
        cls.project.save()
        cls.user = create_restore_user(
            cls.domain,
            username=uuid.uuid4().hex,
        )

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestLiveQuery, cls).tearDownClass()

    def test_clean_owners_after_livequery(self):
        device = MockDevice(self.project, self.user, {"case_sync": LIVEQUERY})
        device.sync()
        with self.assertRaises(RestoreException):
            device.sync(case_sync=CLEAN_OWNERS)


class TestNewSyncSpecifics(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestNewSyncSpecifics, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.project = Domain(name=cls.domain)
        cls.user = create_restore_user(
            cls.domain,
            username=uuid.uuid4().hex,
        )
        cls.user_id = cls.user.user_id

    def test_legacy_support_toggle(self):
        restore_config = RestoreConfig(self.project, restore_user=self.user)
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
        sync_log = deprecated_synclog_from_restore_payload(restore_payload)
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


@use_sql_backend
class TestNewSyncSpecificsSQL(TestNewSyncSpecifics):
    pass
