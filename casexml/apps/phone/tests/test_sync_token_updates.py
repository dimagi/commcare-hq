from django.test import TestCase
import os
import time
from couchforms.util import post_xform_to_couch
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_xml_line_by_line, CaseBlock,\
    check_user_has_case
from casexml.apps.case.signals import process_cases
from casexml.apps.phone.models import SyncLog, CaseState
from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.phone.tests import const
from casexml.apps.phone.tests.dummy import dummy_user
from couchforms.models import XFormInstance
from casexml.apps.case.xml import V2
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.sharedmodels import CommCareCaseIndex

USER_ID = "foo"
PARENT_TYPE = "mother"
        
class SyncTokenUpdateTest(TestCase):
    """
    Tests sync token updates on submission
    """
        
    def setUp(self):
        # clear cases
        for item in XFormInstance.view("couchforms/by_xmlns", include_docs=True, reduce=False).all():
            item.delete()
        for case in CommCareCase.view("case/by_user", reduce=False, include_docs=True).all():
            case.delete()
        for log in SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all():
            log.delete()
        
        self.user = dummy_user() 
        # this creates the initial blank sync token in the database
        generate_restore_payload(self.user)
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        self.sync_log = sync_log
        
    def _createCaseStubs(self, id_list):
        for id in id_list:
            parent = CaseBlock(
                create=True,
                case_id=id,
                user_id=USER_ID,
                case_type=PARENT_TYPE,
                version=V2
            ).as_xml()
            self._postFakeWithSyncToken(parent, self.sync_log.get_id)
        
    def _postWithSyncToken(self, filename, token_id):
        file_path = os.path.join(os.path.dirname(__file__), "data", filename)
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        
        # set last sync token on the form before saving
        form.last_sync_token = token_id
        process_cases(sender="testharness", xform=form)
        
    def _postFakeWithSyncToken(self, caseblock, token_id):
        post_case_blocks([caseblock], form_extras={"last_sync_token": token_id})
        
    def _checkLists(self, l1, l2):
        self.assertEqual(len(l1), len(l2))
        for i in l1:
            self.assertTrue(i in l2, "%s found in %s" % (i, l2))
        for i in l2:
            self.assertTrue(i in l1, "%s found in %s" % (i, l1))
    
    def _testUpdate(self, sync_id, case_id_map, dependent_case_id_map={}):
        sync_log = SyncLog.get(sync_id)
        
        # check case map
        self.assertEqual(len(case_id_map), len(sync_log.cases_on_phone))
        for case_id, indices in case_id_map.items():
            self.assertTrue(sync_log.phone_has_case(case_id))
            state = sync_log.get_case_state(case_id)
            self._checkLists(indices, state.indices)
        
        # check dependent case map
        self.assertEqual(len(dependent_case_id_map), len(sync_log.dependent_cases_on_phone))
        for case_id, indices in dependent_case_id_map.items():
            self.assertTrue(sync_log.phone_has_dependent_case(case_id))
            state = sync_log.get_dependent_case_state(case_id)
            self._checkLists(indices, state.indices)
        
    def testInitialEmpty(self):
        """
        Tests that a newly created sync token has no cases attached to it.
        """
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        self._testUpdate(sync_log.get_id, {}, {})
                         
        
    def testTokenAssociation(self):
        """
        Test that individual create, update, and close submissions update
        the appropriate case lists in the sync token
        """
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
        # a normal update should have no affect
        self._postWithSyncToken("update_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
        # close should remove it from the cases_on_phone list
        # (and currently puts it into the dependent list though this 
        # might change.
        self._postWithSyncToken("close_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {}, {"asdf": []})

    def testMultipleUpdates(self):
        """
        Test that multiple update submissions don't update the case lists 
        and don't create duplicates in them
        """
        
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        self._postWithSyncToken("update_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
        self._postWithSyncToken("update_short_2.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
    def testMultiplePartsSingleSubmit(self):
        """
        Tests a create and update in the same form
        """
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        self._postWithSyncToken("case_create.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"IKA9G79J4HDSPJLG3ER2OHQUY": []})
        
    def testMultipleCases(self):
        """
        Test creating multiple cases from multilple forms
        """
        [sync_log] = SyncLog.view("phone/sync_logs_by_user", include_docs=True, reduce=False).all()
        
        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
        self._postWithSyncToken("case_create.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": [], 
                                           "IKA9G79J4HDSPJLG3ER2OHQUY": []})
    
    def testIndexReferences(self):
        """
        Tests that indices properly get set in the sync log when created. 
        """
        # first create the parent case
        parent_id = "mommy"
        updated_id = "updated_mommy_id"
        new_parent_id = "daddy"
        self._createCaseStubs([parent_id, updated_id, new_parent_id])
        self._testUpdate(self.sync_log.get_id, {parent_id: [], updated_id: [], new_parent_id: []})
        
        # create the child        
        child_id = "baby"
        index_id = 'my_mom_is'
        child = CaseBlock(
            create=True,
            case_id=child_id,
            user_id=USER_ID,
            version=V2,
            index={index_id: (PARENT_TYPE, parent_id)},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        index_ref = CommCareCaseIndex(identifier=index_id,
                                      referenced_type=PARENT_TYPE,
                                      referenced_id=parent_id)
    
        self._testUpdate(self.sync_log.get_id, {parent_id: [], updated_id: [], new_parent_id: [], 
                                                child_id: [index_ref]})
        
        # update the child's index (parent type)
        updated_type = "updated_mother_type"
        child = CaseBlock(create=False, case_id=child_id, user_id=USER_ID, version=V2,
                          index={index_id: (updated_type, parent_id)},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        index_ref = CommCareCaseIndex(identifier=index_id,
                                      referenced_type=updated_type,
                                      referenced_id=parent_id)
    
        self._testUpdate(self.sync_log.get_id, {parent_id: [], updated_id: [], new_parent_id: [], 
                                                child_id: [index_ref]})
        
        # update the child's index (parent id)
        child = CaseBlock(create=False, case_id=child_id, user_id=USER_ID, version=V2,
                          index={index_id: (updated_type, updated_id)},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        index_ref = CommCareCaseIndex(identifier=index_id,
                                      referenced_type=updated_type,
                                      referenced_id=updated_id)
    
        self._testUpdate(self.sync_log.get_id, {parent_id: [], updated_id: [], new_parent_id: [], 
                                                child_id: [index_ref]})
        
        # add new index
        new_index_id = "my_daddy"
        new_index_type = "dad"
        child = CaseBlock(create=False, case_id=child_id, user_id=USER_ID, version=V2,
                          index={new_index_id: (new_index_type, new_parent_id)},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        new_index_ref = CommCareCaseIndex(identifier=new_index_id,
                                          referenced_type=new_index_type,
                                          referenced_id=new_parent_id)
    
        self._testUpdate(self.sync_log.get_id, {parent_id: [], updated_id: [], new_parent_id: [], 
                                                child_id: [index_ref, new_index_ref]})
        
        # delete index
        child = CaseBlock(create=False, case_id=child_id, user_id=USER_ID, version=V2,
                          index={index_id: (updated_type, "")},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        self._testUpdate(self.sync_log.get_id, {parent_id: [], updated_id: [], new_parent_id: [], 
                                                child_id: [new_index_ref]})
    