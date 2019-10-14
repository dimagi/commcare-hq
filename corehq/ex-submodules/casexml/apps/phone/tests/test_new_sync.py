import uuid

from django.test import TestCase

from jsonobject import JsonObject
from six.moves import range

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from casexml.apps.phone.const import CLEAN_OWNERS, LIVEQUERY
from casexml.apps.phone.exceptions import RestoreException
from casexml.apps.phone.models import SimplifiedSyncLog
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

    @classmethod
    def tearDownClass(cls):
        set_request(None)
        super(TestNewSyncSpecifics, cls).tearDownClass()

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
        restore_payload = restore_config.get_payload().as_string().decode('utf-8')
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
