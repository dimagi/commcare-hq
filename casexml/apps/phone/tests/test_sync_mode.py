from django.test import TestCase
import os
import time
from couchforms.util import post_xform_to_couch
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_xml_line_by_line, CaseBlock, \
    check_user_has_case
from casexml.apps.case.signals import process_cases
from casexml.apps.phone.models import SyncLog, CaseState, User
from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.phone.tests import const
from casexml.apps.phone.tests.dummy import dummy_user
from couchforms.models import XFormInstance
from casexml.apps.case.xml import V2
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from datetime import datetime
from xml.etree import ElementTree

USER_ID = "foo"
OTHER_USER_ID = "someone_else"
PARENT_TYPE = "mother"

class SyncBaseTest(TestCase):
    """
    Shared functionality among tests
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
        
    
        
class SyncTokenUpdateTest(SyncBaseTest):
    """
    Tests sync token updates on submission related to the list of cases
    on the phone and the footprint.
    """
        
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
        
        # close parent case and make sure it hangs around because the child
        # is still open
        # todo
        
    def testAssignToNewOwner(self):
        # first create the parent case
        parent_id = "mommy"
        self._createCaseStubs([parent_id])
        self._testUpdate(self.sync_log.get_id, {parent_id: []})
        
        # create the child        
        child_id = "baby"
        index_id = 'my_mom_is'
        self._postFakeWithSyncToken(
            CaseBlock(create=True, case_id=child_id, user_id=USER_ID, version=V2,
                      index={index_id: (PARENT_TYPE, parent_id)},
        ).as_xml(), self.sync_log.get_id)
        
        index_ref = CommCareCaseIndex(identifier=index_id,
                                      referenced_type=PARENT_TYPE,
                                      referenced_id=parent_id)
        # should be there
        self._testUpdate(self.sync_log.get_id, {parent_id: [],
                                                child_id: [index_ref]})
        
        # assign to new owner
        new_owner = "not_mine"
        self._postFakeWithSyncToken(
            CaseBlock(create=False, case_id=child_id, user_id=USER_ID, version=V2,
                      owner_id=new_owner
        ).as_xml(), self.sync_log.get_id)
        
        # should be moved
        self._testUpdate(self.sync_log.get_id, {parent_id: []},
                         {child_id: [index_ref]})
        

class MultiUserSyncTest(SyncBaseTest):
    """
    Tests the interaction of two users in sync mode doing various things
    """
    
    def setUp(self):
        super(MultiUserSyncTest, self).setUp()
        # the other user is an "owner" of the original users cases as well,
        # for convenience
        self.other_user = User(user_id=OTHER_USER_ID, username="ferrel",
                               password="changeme", date_joined=datetime(2011, 6, 9),
                               additional_owner_ids=[USER_ID])
        # this creates the initial blank sync token in the database
        generate_restore_payload(self.other_user)
        self.other_sync_log = SyncLog.last_for_user(OTHER_USER_ID)
    
    def testSharedCase(self):
        # create a case by one user
        case_id = "shared_case"
        self._createCaseStubs([case_id])
        # should sync to the other owner
        expected = CaseBlock(case_id=case_id, version=V2).as_xml()
        check_user_has_case(self, self.other_user, expected, should_have=True,
                            line_by_line=False,
                            restore_id=self.other_sync_log.get_id, version=V2)
        
    def testOtherUserEdits(self):
        # create a case by one user
        case_id = "other_user_edits"
        self._createCaseStubs([case_id])
        
        # sync to the other's phone to be able to edit
        check_user_has_case(self, self.other_user, 
                            CaseBlock(case_id=case_id, version=V2).as_xml(), 
                            should_have=True, line_by_line=False,
                            restore_id=self.other_sync_log.get_id, version=V2)
        
        latest_sync = SyncLog.last_for_user(OTHER_USER_ID)
        # update from another
        self._postFakeWithSyncToken(
            CaseBlock(create=False, case_id=case_id, user_id=OTHER_USER_ID,
                      version=V2, update={'greeting': "Hello!"}
        ).as_xml(), latest_sync.get_id)
        
        # original user syncs again
        # make sure updates take
        updated_case = CaseBlock(create=False, case_id=case_id, user_id=USER_ID,
                                 version=V2, update={'greeting': "Hello!"}).as_xml()
        match = check_user_has_case(self, self.user, updated_case, should_have=True,
                                    line_by_line=False, restore_id=self.sync_log.get_id,
                                    version=V2)
        self.assertTrue("Hello!" in ElementTree.tostring(match))
        
        
    
    def testOtherUserAddsIndex(self):
        # create a case from one user
        case_id = "other_user_adds_index"
        mother_id = "other_user_adds_index_mother"
        self._createCaseStubs([case_id, mother_id])

        # sync to the other's phone to be able to edit
        check_user_has_case(self, self.other_user,
            CaseBlock(case_id=case_id, version=V2).as_xml(),
            should_have=True, line_by_line=False,
            restore_id=self.other_sync_log.get_id, version=V2)

        # update from another, adding an indexed case
        latest_sync = SyncLog.last_for_user(OTHER_USER_ID)
        self._postFakeWithSyncToken(
            CaseBlock(
                create=False,
                case_id=case_id,
                user_id=OTHER_USER_ID,
                version=V2,
                update={'greeting': 'hello'},
                index={'mother': ('mother', mother_id)}
            ).as_xml(),
            latest_sync.get_id
        )

        # original user syncs again
        # make sure index updates take and indexed case also syncs
        mother_case = CaseBlock(create=False, case_id=mother_id, user_id=USER_ID, version=V2).as_xml()
        print ElementTree.tostring(mother_case)
        match = check_user_has_case(self, self.user, mother_case, restore_id=self.sync_log.get_id, version=V2)
    
    def testMultiUserEdits(self):
        # create a case from one user
        case_id = "multi_user_edits"
        self._createCaseStubs([case_id])

        # both users syncs
        generate_restore_payload(self.user)
        generate_restore_payload(self.other_user)
        self.sync_log = SyncLog.last_for_user(USER_ID)
        self.other_sync_log = SyncLog.last_for_user(OTHER_USER_ID)

        # update case from same user
        my_change = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            update={'greeting': 'hello'}
        ).as_xml()
        self._postFakeWithSyncToken(
            my_change,
            self.sync_log.get_id
        )

        # update from another user
        their_change = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            update={'greeting_2': 'hello'}
        ).as_xml()
        self._postFakeWithSyncToken(
            their_change,
            self.other_sync_log.get_id
        )

        # original user syncs again
        # make sure updates both appear (and merge?)
        joint_change = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            update={
                'greeting': 'hello',
                'greeting_2': 'hello'
            },
            owner_id='',
            case_name='',
            case_type='mother',
        ).as_xml()
        check_user_has_case(self, self.user, joint_change, restore_id=self.sync_log.get_id, version=V2)
        check_user_has_case(self, self.other_user, joint_change, restore_id=self.other_sync_log.get_id, version=V2)

    def testOtherUserCloses(self):
        # create a case from one user
        # close case from another user
        # original user syncs again
        # make sure close block appears
        pass
    
    def testOtherUserUpdatesUnowned(self):
        # create a case from one user and assign ownership elsewhere
        # update from another user
        # original user syncs again
        # make sure there are no new changes
        pass
        
    def testIndexesSync(self):
        # create a parent and child case (with index) from one user
        # assign just the child case to a second user
        # second user syncs
        # make sure both cases restore
        pass
        
    def testOtherUserUpdatesIndex(self):
        # create a parent and child case (with index) from one user
        # assign the parent case away from same user
        # original user syncs again
        # make sure there are no new changes
        # update the parent case from another user
        # make sure the indexed case syncs again
        pass
    
    def testOtherUserReassignsIndexed(self):
        # create a parent and child case (with index) from one user
        # assign the parent case away from the same user
        # change the child's owner from another user
        # also change the parent from the second user
        # original user syncs again
        # both cases should sync to original user with updated ownership / edits
        # change the parent again from the second user
        # original user syncs again
        # should be no changes
        # change the child again from the second user
        # original user syncs again
        # should be no changes
        # change owner of child back to orginal user from second user
        # original user syncs again
        # both cases should now sync
        pass
    
    
