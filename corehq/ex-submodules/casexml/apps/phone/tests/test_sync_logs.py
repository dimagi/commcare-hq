from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import TestCase, SimpleTestCase
from casexml.apps.case.xml import V1
from casexml.apps.phone.models import SyncLog, CaseState
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.phone.restore import RestoreParams, RestoreConfig
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.phone.utils import MockDevice
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain


class PhoneFootprintTest(SimpleTestCase):

    def test_empty(self):
        log = SyncLog()
        self.assertEqual(0, len(log.get_footprint_of_cases_on_phone()))
        
        log = SyncLog(cases_on_phone=[])
        self.assertEqual(0, len(log.get_footprint_of_cases_on_phone()))
        
        log = SyncLog(dependent_cases_on_phone=[])
        self.assertEqual(0, len(log.get_footprint_of_cases_on_phone()))
        
        log = SyncLog(cases_on_phone=[], dependent_cases_on_phone=[])
        self.assertEqual(0, len(log.get_footprint_of_cases_on_phone()))
    
    def test_cases_in_footprint(self):
        log = SyncLog(cases_on_phone=[CaseState(case_id="c1", indices=[]),
                                      CaseState(case_id="c2", indices=[])])
        self.assertEqual(2, len(log.get_footprint_of_cases_on_phone()))
        
        log.cases_on_phone.append(CaseState(case_id="c3", indices=[]))
        self.assertEqual(3, len(log.get_footprint_of_cases_on_phone()))
        
    def test_dependent_cases(self):
        log = SyncLog(cases_on_phone=[CaseState(case_id="c1", 
                                                indices=[CommCareCaseIndex(identifier="d1-id",
                                                                           referenced_id="d1")])],
                      dependent_cases_on_phone=[CaseState(case_id="d1", indices=[]),
                                                CaseState(case_id="d2", indices=[])])
        
        # d1 counts because it's referenced, d2 doesn't
        self.assertEqual(2, len(log.get_footprint_of_cases_on_phone()))
        self.assertTrue("d1" in log.get_footprint_of_cases_on_phone())
        self.assertFalse("d2" in log.get_footprint_of_cases_on_phone())
        
    def test_archive(self):
        log = SyncLog(cases_on_phone=[CaseState(case_id="c1", 
                                                indices=[CommCareCaseIndex(identifier="d1-id",
                                                                           referenced_id="d1")]),
                                      CaseState(case_id="c2", 
                                                indices=[CommCareCaseIndex(identifier="d1-id",
                                                                           referenced_id="d1"),
                                                         CommCareCaseIndex(identifier="d2-id",
                                                                           referenced_id="d2")]),
                                      CaseState(case_id="c3", indices=[])],
                      dependent_cases_on_phone=[CaseState(case_id="d1", indices=[]),
                                                CaseState(case_id="d2", indices=[])])
        self.assertEqual(5, len(log.get_footprint_of_cases_on_phone()))
        
        self.assertTrue("c3" in log.get_footprint_of_cases_on_phone())
        log.archive_case("c3")
        self.assertEqual(4, len(log.get_footprint_of_cases_on_phone()))
        self.assertFalse("c3" in log.get_footprint_of_cases_on_phone())
        
        self.assertTrue("c2" in log.get_footprint_of_cases_on_phone())
        self.assertTrue("d2" in log.get_footprint_of_cases_on_phone())
        log.archive_case("c2")
        self.assertEqual(2, len(log.get_footprint_of_cases_on_phone()))
        self.assertFalse("c2" in log.get_footprint_of_cases_on_phone())
        self.assertFalse("d2" in log.get_footprint_of_cases_on_phone())
        
        self.assertTrue("c1" in log.get_footprint_of_cases_on_phone())
        self.assertTrue("d1" in log.get_footprint_of_cases_on_phone())
        log.archive_case("c1")
        self.assertEqual(0, len(log.get_footprint_of_cases_on_phone()))


class SyncLogModelTest(TestCase):
    domain = 'sync-log-model-test'

    @classmethod
    def setUpClass(cls):
        super(SyncLogModelTest, cls).setUpClass()
        cls.project = Domain(name=cls.domain)
        cls.project.save()
        cls.restore_user = create_restore_user(cls.domain, username=uuid.uuid4().hex)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(SyncLogModelTest, cls).tearDownClass()

    def test_basic_properties(self):
        # kick off a restore to generate the sync log
        device = MockDevice(self.project, self.restore_user)
        sync_log = device.sync(version=V1, items=True).log
        self.assertEqual(self.restore_user.user_id, sync_log.user_id)
        self.assertEqual(self.restore_user.domain, sync_log.domain)

    def test_build_id(self):
        app = Application(domain=self.domain)
        app.save()
        config = RestoreConfig(
            project=self.project,
            restore_user=self.restore_user,
            params=RestoreParams(
                app=app,
            ),
        )
        config.get_payload()  # this generates the sync log
        sync_log = SyncLog.last_for_user(self.restore_user.user_id)
        self.assertEqual(self.restore_user.user_id, sync_log.user_id)
        self.assertEqual(self.restore_user.domain, sync_log.domain)
        self.assertEqual(app._id, sync_log.build_id)
        self.addCleanup(app.delete)
