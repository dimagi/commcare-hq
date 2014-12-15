from django.test.utils import override_settings
from django.test import TestCase
import os
from casexml.apps.case.mock import CaseBlock
from casexml.apps.phone.tests.utils import synclog_from_restore_payload
from couchforms.tests.testutils import post_xform_to_couch
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import (check_user_has_case, delete_all_sync_logs,
    delete_all_xforms, delete_all_cases, assert_user_doesnt_have_case,
    assert_user_has_case)
from casexml.apps.case import process_cases
from casexml.apps.phone.models import SyncLog, User
from casexml.apps.phone.restore import generate_restore_payload, RestoreConfig
from dimagi.utils.parsing import json_format_datetime
from couchforms.models import XFormInstance
from casexml.apps.case.xml import V2, V1
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from datetime import datetime
from xml.etree import ElementTree

USER_ID = "main_user"
OTHER_USER_ID = "someone_else"
SHARED_ID = "our_group"
PARENT_TYPE = "mother"


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class SyncBaseTest(TestCase):
    """
    Shared functionality among tests
    """

    def setUp(self):
        delete_all_cases()
        delete_all_xforms()
        delete_all_sync_logs()

        self.user = User(user_id=USER_ID, username="syncguy", 
                         password="changeme", date_joined=datetime(2011, 6, 9)) 
        # this creates the initial blank sync token in the database
        restore_config = RestoreConfig(self.user)
        self.sync_log = synclog_from_restore_payload(restore_config.get_payload())

    def _createCaseStubs(self, id_list, user_id=USER_ID, owner_id=USER_ID):
        for id in id_list:
            caseblock = CaseBlock(
                create=True,
                case_id=id,
                user_id=user_id,
                owner_id=owner_id,
                case_type=PARENT_TYPE,
                version=V2
            ).as_xml()
            self._postFakeWithSyncToken(caseblock, self.sync_log.get_id)
        
    def _postWithSyncToken(self, filename, token_id):
        file_path = os.path.join(os.path.dirname(__file__), "data", filename)
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        
        # set last sync token on the form before saving
        form.last_sync_token = token_id
        process_cases(form)
        return form

    def _postFakeWithSyncToken(self, caseblock, token_id):
        return post_case_blocks([caseblock], form_extras={"last_sync_token": token_id})

    def _checkLists(self, l1, l2):
        self.assertEqual(len(l1), len(l2))
        for i in l1:
            self.assertTrue(i in l2, "%s found in %s" % (i, l2))
        for i in l2:
            self.assertTrue(i in l1, "%s found in %s" % (i, l1))
    
    def _testUpdate(self, sync_id, case_id_map, dependent_case_id_map=None):
        dependent_case_id_map = dependent_case_id_map or {}
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
    
    def testOwnUpdatesDontSync(self):
        case_id = "own_updates_dont_sync"
        self._createCaseStubs([case_id])
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        
        update_block = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            update={"greeting": "hello"}
        ).as_xml()
        self._postFakeWithSyncToken(update_block, self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        reassign_block = CaseBlock(
            create=False,
            case_id=case_id,
            owner_id=OTHER_USER_ID,
            version=V2
        ).as_xml()
        self._postFakeWithSyncToken(reassign_block, self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

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
        
    def testClosedParentIndex(self):
        """
        Tests that things work properly when you have a reference to the parent
        case in a child, even if it's closed.
        """
        # first create the parent case
        parent_id = "mommy"
        self._createCaseStubs([parent_id])
        self._testUpdate(self.sync_log.get_id, {parent_id: []})
        
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
    
        self._testUpdate(self.sync_log.get_id, {parent_id: [], 
                                                child_id: [index_ref]})
        
        # close the mother case
        close = CaseBlock(create=False, case_id=parent_id, user_id=USER_ID, 
                          version=V2, close=True
        ).as_xml()
        self._postFakeWithSyncToken(close, self.sync_log.get_id)
        self._testUpdate(self.sync_log.get_id, {child_id: [index_ref]},
                         {parent_id: []})
        
        # try a clean restore again
        assert_user_has_case(self, self.user, parent_id)
        assert_user_has_case(self, self.user, child_id)

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

    def testArchiveUpdates(self):
        """
        Tests that archiving a form (and changing a case) causes the
        case to be included in the next sync.
        """
        case_id = "archive_syncs"
        self._createCaseStubs([case_id])
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        update_block = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            update={"greeting": "hello"}
        ).as_xml()
        form = self._postFakeWithSyncToken(update_block, self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        form.archive()
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id, purge_restore_cache=True)


class SyncTokenCachingTest(SyncBaseTest):

    def testCaching(self):
        self.assertFalse(self.sync_log.has_cached_payload(V2))
        # first request should populate the cache
        original_payload = RestoreConfig(
            self.user, version=V2,
            restore_id=self.sync_log._id,
        ).get_payload()
        next_sync_log = synclog_from_restore_payload(original_payload)

        self.sync_log = SyncLog.get(self.sync_log._id)
        self.assertTrue(self.sync_log.has_cached_payload(V2))

        # a second request with the same config should be exactly the same
        cached_payload = RestoreConfig(
            self.user, version=V2,
            restore_id=self.sync_log._id,
        ).get_payload()
        self.assertEqual(original_payload, cached_payload)

        # caching a different version should also produce something new
        versioned_payload = RestoreConfig(
            self.user, version=V1,
            restore_id=self.sync_log._id,
        ).get_payload()
        self.assertNotEqual(original_payload, versioned_payload)
        versioned_sync_log = synclog_from_restore_payload(versioned_payload)
        self.assertNotEqual(next_sync_log._id, versioned_sync_log._id)

    def testCacheInvalidation(self):
        original_payload = RestoreConfig(
            self.user, version=V2,
            restore_id=self.sync_log._id,
        ).get_payload()
        self.sync_log = SyncLog.get(self.sync_log._id)
        self.assertTrue(self.sync_log.has_cached_payload(V2))

        # posting a case associated with this sync token should invalidate the cache
        case_id = "cache_invalidation"
        self._createCaseStubs([case_id])
        self.sync_log = SyncLog.get(self.sync_log._id)
        self.assertFalse(self.sync_log.has_cached_payload(V2))

        # resyncing should recreate the cache
        next_payload = RestoreConfig(
            self.user, version=V2,
            restore_id=self.sync_log._id,
        ).get_payload()
        self.sync_log = SyncLog.get(self.sync_log._id)
        self.assertTrue(self.sync_log.has_cached_payload(V2))
        self.assertNotEqual(original_payload, next_payload)
        self.assertFalse(case_id in original_payload)
        # since it was our own update, it shouldn't be in the new payload either
        self.assertFalse(case_id in next_payload)
        # we can be explicit about why this is the case
        self.assertTrue(self.sync_log.phone_has_case(case_id))

    def testCacheNonInvalidation(self):
        original_payload = RestoreConfig(
            self.user, version=V2,
            restore_id=self.sync_log._id,
        ).get_payload()
        self.sync_log = SyncLog.get(self.sync_log._id)
        self.assertTrue(self.sync_log.has_cached_payload(V2))

        # posting a case associated with this sync token should invalidate the cache
        # submitting a case not with the token will not touch the cache for that token
        case_id =  "cache_noninvalidation"
        post_case_blocks([CaseBlock(
            create=True,
            case_id=case_id,
            user_id=self.user.user_id,
            owner_id=self.user.user_id,
            case_type=PARENT_TYPE,
            version=V2,
        ).as_xml()])
        next_payload = RestoreConfig(
            self.user, version=V2,
            restore_id=self.sync_log._id,
        ).get_payload()
        self.assertEqual(original_payload, next_payload)
        self.assertFalse(case_id in next_payload)


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
                               additional_owner_ids=[SHARED_ID])
        
        # this creates the initial blank sync token in the database
        self.other_sync_log = synclog_from_restore_payload(generate_restore_payload(self.other_user))
        
        self.assertTrue(SHARED_ID in self.other_sync_log.owner_ids_on_phone)
        self.assertTrue(OTHER_USER_ID in self.other_sync_log.owner_ids_on_phone)
        
        self.user.additional_owner_ids = [SHARED_ID]
        self.sync_log = synclog_from_restore_payload(generate_restore_payload(self.user))
        self.assertTrue(SHARED_ID in self.sync_log.owner_ids_on_phone)
        self.assertTrue(USER_ID in self.sync_log.owner_ids_on_phone)
        
        
    def testSharedCase(self):
        # create a case by one user
        case_id = "shared_case"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)
        # should sync to the other owner
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)
        
    def testOtherUserEdits(self):
        # create a case by one user
        case_id = "other_user_edits"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)
        
        # sync to the other's phone to be able to edit
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)
        
        latest_sync = SyncLog.last_for_user(OTHER_USER_ID)
        # update from another
        self._postFakeWithSyncToken(
            CaseBlock(create=False, case_id=case_id, user_id=OTHER_USER_ID,
                      version=V2, update={'greeting': "Hello!"}
        ).as_xml(), latest_sync.get_id)
        
        # original user syncs again
        # make sure updates take
        match = assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        self.assertTrue("Hello!" in ElementTree.tostring(match))
    
    def testOtherUserAddsIndex(self):
        time = datetime.now()

        # create a case from one user
        case_id = "other_user_adds_index"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)

        # sync to the other's phone to be able to edit
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

        latest_sync = SyncLog.last_for_user(OTHER_USER_ID)
        mother_id = "other_user_adds_index_mother"

        parent_case = CaseBlock(
            create=True,
            date_modified=time,
            case_id=mother_id,
            user_id=OTHER_USER_ID,
            case_type=PARENT_TYPE,
            version=V2,
        ).as_xml(format_datetime=json_format_datetime)

        self._postFakeWithSyncToken(
            parent_case,
            latest_sync.get_id
        )
        # the original user should not get the parent case
        assert_user_doesnt_have_case(self, self.user, mother_id, restore_id=self.sync_log.get_id)

        # update the original case from another, adding an indexed case
        self._postFakeWithSyncToken(
            CaseBlock(
                create=False,
                case_id=case_id,
                user_id=OTHER_USER_ID,
                owner_id=USER_ID,
                version=V2,
                index={'mother': ('mother', mother_id)}
            ).as_xml(format_datetime=json_format_datetime),
            latest_sync.get_id
        )

        # original user syncs again
        # make sure index updates take and indexed case also syncs
        expected_parent_case = CaseBlock(
            create=True,
            date_modified=time,
            case_id=mother_id,
            user_id=OTHER_USER_ID,
            case_type=PARENT_TYPE,
            owner_id=OTHER_USER_ID,
            version=V2,
        ).as_xml(format_datetime=json_format_datetime)

        check_user_has_case(self, self.user, expected_parent_case,
                            restore_id=self.sync_log.get_id, version=V2,
                            purge_restore_cache=True)
        orig = assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        self.assertTrue("index" in ElementTree.tostring(orig))

    def testMultiUserEdits(self):
        time = datetime.now()

        # create a case from one user
        case_id = "multi_user_edits"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)

        # both users syncs
        self.sync_log = synclog_from_restore_payload(generate_restore_payload(self.user))
        self.other_sync_log = synclog_from_restore_payload(generate_restore_payload(self.other_user))

        # update case from same user
        my_change = CaseBlock(
            create=False,
            date_modified=time,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            update={'greeting': 'hello'}
        ).as_xml(format_datetime=json_format_datetime)
        self._postFakeWithSyncToken(
            my_change,
            self.sync_log.get_id
        )

        # update from another user
        their_change = CaseBlock(
            create=False,
            date_modified=time,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            update={'greeting_2': 'hello'}
        ).as_xml(format_datetime=json_format_datetime)
        self._postFakeWithSyncToken(
            their_change,
            self.other_sync_log.get_id
        )

        # original user syncs again
        # make sure updates both appear (and merge?)
        joint_change = CaseBlock(
            create=False,
            date_modified=time,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            update={
                'greeting': 'hello',
                'greeting_2': 'hello'
            },
            owner_id=SHARED_ID,
            case_name='',
            case_type='mother',
        ).as_xml(format_datetime=json_format_datetime)

        check_user_has_case(self, self.user, joint_change, restore_id=self.sync_log.get_id, version=V2)
        check_user_has_case(self, self.other_user, joint_change, restore_id=self.other_sync_log.get_id, version=V2)

    def testOtherUserCloses(self):
        # create a case from one user
        case_id = "other_user_closes"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)

        # sync then close case from another user
        self.other_sync_log = synclog_from_restore_payload(generate_restore_payload(self.other_user))
        close_block = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            close=True
        ).as_xml()
        self._postFakeWithSyncToken(
            close_block,
            self.other_sync_log.get_id
        )

        # original user syncs again
        # make sure close block appears
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

    def testOtherUserUpdatesUnowned(self):
        # create a case from one user and assign ownership elsewhere
        case_id = "other_user_updates_unowned"
        self._createCaseStubs([case_id], owner_id=OTHER_USER_ID)

        # sync and update from another user
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

        self.other_sync_log = SyncLog.last_for_user(OTHER_USER_ID)
        update = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=OTHER_USER_ID,
            version=V2,
            update={'greeting': 'hello'}
        ).as_xml()
        self._postFakeWithSyncToken(
            update,
            self.other_sync_log.get_id
        )
        
        # original user syncs again
        # make sure there are no new changes
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        
                
    def testIndexesSync(self):
        # create a parent and child case (with index) from one user
        parent_id = "indexes_sync_parent"
        case_id = "indexes_sync"
        self._createCaseStubs([parent_id])
        child = CaseBlock(
            create=True,
            case_id=case_id,
            user_id=USER_ID,
            owner_id=USER_ID,
            version=V2,
            index={'mother': ('mother', parent_id)}
        ).as_xml() 
        self._postFakeWithSyncToken(child, self.sync_log.get_id)

        # make sure the second user doesn't get either
        assert_user_doesnt_have_case(self, self.other_user, parent_id, restore_id=self.other_sync_log.get_id)
        assert_user_doesnt_have_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

        # assign just the child case to a second user
        child_update = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            owner_id=OTHER_USER_ID,
            version=V2,
            update={"greeting": "hello"}
        ).as_xml() 
        self._postFakeWithSyncToken(child_update, self.sync_log.get_id)
        # second user syncs
        # make sure both cases restore
        assert_user_has_case(self, self.other_user, parent_id, restore_id=self.other_sync_log.get_id,
                             purge_restore_cache=True)
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

    def testOtherUserUpdatesIndex(self):
        # create a parent and child case (with index) from one user
        parent_id = "other_updates_index_parent"
        case_id = "other_updates_index_child"
        self._createCaseStubs([parent_id])

        child = CaseBlock(
            create=True,
            case_id=case_id,
            user_id=USER_ID,
            owner_id=USER_ID,
            version=V2,
            index={'mother': ('mother', parent_id)}
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)

        assert_user_doesnt_have_case(self, self.user, parent_id, restore_id=self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        
        # assign the parent case away from same user
        parent_update = CaseBlock(
            create=False, 
            case_id=parent_id,
            user_id=USER_ID, 
            owner_id=OTHER_USER_ID,
            update={"greeting": "hello"}, 
            version=V2).as_xml()
        self._postFakeWithSyncToken(parent_update, self.sync_log.get_id)
        
        self.sync_log = SyncLog.get(self.sync_log.get_id)
        
        # these tests added to debug another issue revealed by this test
        self.assertTrue(self.sync_log.phone_has_case(case_id))
        self.assertTrue(self.sync_log.phone_has_dependent_case(parent_id))
        self.assertTrue(self.sync_log.phone_is_holding_case(case_id))
        self.assertTrue(self.sync_log.phone_is_holding_case(parent_id))
        
        # original user syncs again
        # make sure there are no new changes
        assert_user_doesnt_have_case(self, self.user, parent_id, restore_id=self.sync_log.get_id,
                                     purge_restore_cache=True)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        assert_user_has_case(self, self.other_user, parent_id, restore_id=self.other_sync_log.get_id,
                             purge_restore_cache=True)
        # update the parent case from another user
        self.other_sync_log = SyncLog.last_for_user(OTHER_USER_ID)
        other_parent_update = CaseBlock(
            create=False,
            case_id=parent_id,
            user_id=OTHER_USER_ID,
            update={"greeting2": "hi"},
            version=V2
        ).as_xml()
        self._postFakeWithSyncToken(other_parent_update, self.other_sync_log.get_id)
        
        # make sure the indexed case syncs again
        self.sync_log = SyncLog.last_for_user(USER_ID)
        assert_user_has_case(self, self.user, parent_id, restore_id=self.sync_log.get_id,
                             purge_restore_cache=True)

    def testOtherUserReassignsIndexed(self):
        # create a parent and child case (with index) from one user
        parent_id = "other_reassigns_index_parent"
        case_id = "other_reassigns_index_child"
        self._createCaseStubs([parent_id])
        child = CaseBlock(
            create=True,
            case_id=case_id,
            user_id=USER_ID,
            owner_id=SHARED_ID,
            version=V2,
            index={'mother': ('mother', parent_id)}
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        
        
        # assign the parent case away from the same user
        parent_update = CaseBlock(
            create=False, 
            case_id=parent_id,
            user_id=USER_ID, 
            owner_id=OTHER_USER_ID,
            update={"greeting": "hello"}, 
            version=V2).as_xml()
        self._postFakeWithSyncToken(parent_update, self.sync_log.get_id)
        
        # sync cases to second user
        self.other_sync_log = synclog_from_restore_payload(generate_restore_payload(self.other_user))
        # change the child's owner from another user
        child_reassignment = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=OTHER_USER_ID,
            owner_id=OTHER_USER_ID,
            version=V2,
            update={"childgreeting": "hi!"}, 
        ).as_xml()
        self._postFakeWithSyncToken(child_reassignment, self.other_sync_log.get_id)
        
        # also change the parent from the second user
        other_parent_update = CaseBlock(
            create=False, 
            case_id=parent_id,
            user_id=OTHER_USER_ID, 
            owner_id=OTHER_USER_ID,
            update={"other_greeting": "something new"}, 
            version=V2).as_xml()
        self._postFakeWithSyncToken(other_parent_update, self.other_sync_log.get_id)
        
        # original user syncs again
        self.sync_log = SyncLog.last_for_user(self.user.user_id)
        # both cases should sync to original user with updated ownership / edits
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        assert_user_has_case(self, self.user, parent_id, restore_id=self.sync_log.get_id)

        # Ghetto
        payload = generate_restore_payload(self.user, self.sync_log.get_id, 
                                           version=V2)
        self.assertTrue("something new" in payload)
        self.assertTrue("hi!" in payload)
        
        # change the parent again from the second user
        other_parent_update = CaseBlock(
            create=False, 
            case_id=parent_id,
            user_id=OTHER_USER_ID, 
            owner_id=OTHER_USER_ID,
            update={"other_greeting": "something different"}, 
            version=V2).as_xml()
        self._postFakeWithSyncToken(other_parent_update, self.other_sync_log.get_id)
        
        
        # original user syncs again
        self.sync_log = SyncLog.last_for_user(self.user.user_id)
        # should be no changes
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, parent_id, restore_id=self.sync_log.get_id)

        # change the child again from the second user
        other_child_update = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=OTHER_USER_ID,
            owner_id=OTHER_USER_ID,
            version=V2,
            update={"childgreeting": "hi changed!"}, 
        ).as_xml()
        self._postFakeWithSyncToken(other_child_update, self.other_sync_log.get_id)
        
        # original user syncs again
        self.sync_log = SyncLog.last_for_user(self.user.user_id)
        # should be no changes
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, parent_id, restore_id=self.sync_log.get_id)

        # change owner of child back to orginal user from second user
        child_reassignment = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=OTHER_USER_ID,
            owner_id=USER_ID,
            version=V2
        ).as_xml()
        self._postFakeWithSyncToken(child_reassignment, self.other_sync_log.get_id)
        
        # original user syncs again
        self.sync_log = SyncLog.last_for_user(self.user.user_id)
        # both cases should now sync
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        assert_user_has_case(self, self.user, parent_id, restore_id=self.sync_log.get_id)

        # ghetto
        payload = generate_restore_payload(self.user, self.sync_log.get_id, 
                                           version=V2)
        self.assertTrue("something different" in payload)
        self.assertTrue("hi changed!" in payload)
    
    def testComplicatedGatesBug(self):
        # found this bug in the wild, used the real (test) forms to fix it
        # just running through this test used to fail hard, even though there
        # are no asserts
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        folder_path = os.path.join("bugs", "dependent_case_conflicts")
        files = ["reg1.xml", "reg2.xml", "cf.xml", "close.xml"]
        for f in files:
            form = self._postWithSyncToken(os.path.join(folder_path, f), self.sync_log.get_id)
            form = XFormInstance.get(form.get_id)
            self.assertFalse(hasattr(form, "problem"))
            self.sync_log = synclog_from_restore_payload(generate_restore_payload(self.user, version="2.0"))


class SyncTokenReprocessingTest(SyncBaseTest):
    """
    Tests sync token logic for fixing itself when it gets into a bad state.
    """

    def testUpdateNonExisting(self):
        case_id = 'non_existent'
        caseblock = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            owner_id=USER_ID,
            case_type=PARENT_TYPE,
            version=V2
        ).as_xml()
        try:
            self._postFakeWithSyncToken(caseblock, self.sync_log.get_id)
            self.fail('posting an update to a non-existant case should fail')
        except AssertionError:
            # this should fail because it's a true error
            pass


    def testShouldHaveCase(self):
        case_id = "should_have"
        self._createCaseStubs([case_id])
        sync_log = SyncLog.get(self.sync_log._id)
        self.assertEqual(1, len(sync_log.cases_on_phone))
        self.assertEqual(case_id, sync_log.cases_on_phone[0].case_id)

        # manually delete it and then try to update
        sync_log.cases_on_phone = []
        sync_log.save()

        update = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            owner_id=USER_ID,
            case_type=PARENT_TYPE,
            version=V2,
            update={'something': "changed"},
        ).as_xml()

        # this should work because it should magically fix itself
        self._postFakeWithSyncToken(update, self.sync_log.get_id)
        sync_log = SyncLog.get(self.sync_log._id)
        self.assertFalse(getattr(sync_log, 'has_assert_errors', False))

    def testCodependencies(self):

        case_id1 = 'bad1'
        case_id2 = 'bad2'
        initial_caseblocks = [CaseBlock(
            create=True,
            case_id=case_id,
            user_id='not_me',
            owner_id='not_me',
            case_type=PARENT_TYPE,
            version=V2
        ).as_xml() for case_id in [case_id1, case_id2]]

        post_case_blocks(
            initial_caseblocks,
        )

        def _get_bad_caseblocks(ids):
            return [CaseBlock(
                create=False,
                case_id=id,
                user_id=USER_ID,
                owner_id=USER_ID,
                case_type=PARENT_TYPE,
                version=V2
            ).as_xml() for id in ids]

        try:
            post_case_blocks(
                _get_bad_caseblocks([case_id1, case_id2]),
                form_extras={ "last_sync_token": self.sync_log._id }
            )
            self.fail('posting an update to non-existant cases should fail')
        except AssertionError:
            # this should fail because it's a true error
            pass

        try:
            post_case_blocks(
                _get_bad_caseblocks([case_id2, case_id1]),
                form_extras={ "last_sync_token": self.sync_log._id }
            )
            self.fail('posting an update to non-existant cases should fail')
        except AssertionError:
            # this should fail because it's a true error
            pass
