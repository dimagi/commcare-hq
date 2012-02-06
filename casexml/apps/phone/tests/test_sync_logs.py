from django.test import TestCase
from casexml.apps.phone.models import SyncLog, CaseState
from casexml.apps.case.sharedmodels import CommCareCaseIndex

class PhoneFootprintTest(TestCase):
    
    def setUp(self):
        # clear sync logs
        for log in SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all():
            log.delete()
        
    
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
        