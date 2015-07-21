import uuid
from couchdbkit import ResourceNotFound
from django.test.utils import override_settings
from django.test import TestCase
import os
from casexml.apps.phone.exceptions import MissingSyncLog, RestoreException
from casexml.apps.phone.tests.restore_test_utils import run_with_all_restore_configs
from casexml.apps.phone.tests.utils import get_exactly_one_wrapped_sync_log, generate_restore_payload
from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure, CaseRelationship
from casexml.apps.phone.tests.utils import synclog_from_restore_payload
from corehq.apps.domain.models import Domain
from corehq.toggles import LOOSE_SYNC_TOKEN_VALIDATION
from couchforms.tests.testutils import post_xform_to_couch
from casexml.apps.case.tests.util import (check_user_has_case, delete_all_sync_logs,
    delete_all_xforms, delete_all_cases, assert_user_doesnt_have_case,
    assert_user_has_case, TEST_DOMAIN_NAME, assert_user_has_cases)
from casexml.apps.case.xform import process_cases
from casexml.apps.phone.models import SyncLog, User, get_properly_wrapped_sync_log, SimplifiedSyncLog, \
    AbstractSyncLog
from casexml.apps.phone.restore import CachedResponse, RestoreConfig, RestoreParams, RestoreCacheSettings
from dimagi.utils.parsing import json_format_datetime
from couchforms.models import XFormInstance
from casexml.apps.case.xml import V2, V1
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from datetime import datetime

USER_ID = "main_user"
USERNAME = "syncguy"
OTHER_USER_ID = "someone_else"
OTHER_USERNAME = "ferrel"
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
        self.project = Domain(name=TEST_DOMAIN_NAME)
        self.user = User(user_id=USER_ID, username=USERNAME,
                         password="changeme", date_joined=datetime(2011, 6, 9))
        # this creates the initial blank sync token in the database
        restore_config = RestoreConfig(self.project, user=self.user)
        self.sync_log = synclog_from_restore_payload(restore_config.get_payload().as_string())
        self.factory = CaseFactory(
            case_defaults={
                'user_id': USER_ID,
                'owner_id': USER_ID,
                'case_type': PARENT_TYPE,
            },
            form_extras={
                'last_sync_token': self.sync_log._id
            }
        )

    def tearDown(self):
        restore_config = RestoreConfig(project=self.project, user=self.user)
        restore_config.cache.delete(restore_config._initial_cache_key())

    def _createCaseStubs(self, id_list, **kwargs):
        case_attrs = {'create': True}
        case_attrs.update(kwargs)
        return self.factory.create_or_update_cases(
            [CaseStructure(case_id=case_id, attrs=case_attrs) for case_id in id_list],
        )

    def _postWithSyncToken(self, filename, token_id):
        file_path = os.path.join(os.path.dirname(__file__), "data", filename)
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        
        # set last sync token on the form before saving
        form.last_sync_token = token_id
        process_cases(form)
        return form

    def _postFakeWithSyncToken(self, caseblocks, token_id):
        if not isinstance(caseblocks, list):
            # can't use list(caseblocks) since that returns children of the node
            # http://lxml.de/tutorial.html#elements-are-lists
            caseblocks = [caseblocks]
        return post_case_blocks(caseblocks, form_extras={"last_sync_token": token_id})

    def _checkLists(self, l1, l2, msg=None):
        self.assertEqual(set(l1), set(l2), msg)

    def _testUpdate(self, sync_log_or_id, case_id_map, dependent_case_id_map=None):
        dependent_case_id_map = dependent_case_id_map or {}
        if isinstance(sync_log_or_id, AbstractSyncLog):
            sync_log = sync_log_or_id
        else:
            sync_log = get_properly_wrapped_sync_log(sync_log_or_id)

        if isinstance(sync_log, SimplifiedSyncLog):
            all_ids = {}
            all_ids.update(case_id_map)
            all_ids.update(dependent_case_id_map)
            self.assertEqual(set(all_ids), sync_log.case_ids_on_phone)
            self.assertEqual(set(dependent_case_id_map.keys()), sync_log.dependent_case_ids_on_phone)
            for case_id, indices in case_id_map.items():
                if indices:
                    index_ids = [i.referenced_id for i in case_id_map[case_id]]
                    self._checkLists(index_ids, sync_log.index_tree.indices[case_id].values(),
                                     'case {} has unexpected indices'.format(case_id))
            for case_id, indices in dependent_case_id_map.items():
                if indices:
                    index_ids = [i.referenced_id for i in case_id_map[case_id]]
                    self._checkLists(index_ids, sync_log.index_tree.indices[case_id].values())

        else:
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

            # test migration of old to new by migrating and testing again.
            # this is a lazy way of running tests on a variety of edge cases
            # without having to write explicit tests for the migration
            migrated_sync_log = SimplifiedSyncLog.from_other_format(sync_log)
            self._testUpdate(migrated_sync_log, case_id_map, dependent_case_id_map)

    
class SyncTokenUpdateTest(SyncBaseTest):
    """
    Tests sync token updates on submission related to the list of cases
    on the phone and the footprint.
    """
        
    @run_with_all_restore_configs
    def testInitialEmpty(self):
        """
        Tests that a newly created sync token has no cases attached to it.
        """
        sync_log = get_exactly_one_wrapped_sync_log()
        self._testUpdate(sync_log.get_id, {}, {})
                         
    @run_with_all_restore_configs
    def testTokenAssociation(self):
        """
        Test that individual create, update, and close submissions update
        the appropriate case lists in the sync token
        """
        sync_log = get_exactly_one_wrapped_sync_log()
        
        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
        # a normal update should have no affect
        self._postWithSyncToken("update_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
        # close should remove it from the cases_on_phone list
        # (and currently puts it into the dependent list though this 
        # might change.
        self._postWithSyncToken("close_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {}, {})

    @run_with_all_restore_configs
    def testMultipleUpdates(self):
        """
        Test that multiple update submissions don't update the case lists
        and don't create duplicates in them
        """
        sync_log = get_exactly_one_wrapped_sync_log()

        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        self._postWithSyncToken("update_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
        self._postWithSyncToken("update_short_2.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
    @run_with_all_restore_configs
    def testMultiplePartsSingleSubmit(self):
        """
        Tests a create and update in the same form
        """
        sync_log = get_exactly_one_wrapped_sync_log()

        self._postWithSyncToken("case_create.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"IKA9G79J4HDSPJLG3ER2OHQUY": []})
        
    @run_with_all_restore_configs
    def testMultipleCases(self):
        """
        Test creating multiple cases from multilple forms
        """
        sync_log = get_exactly_one_wrapped_sync_log()
        
        self._postWithSyncToken("create_short.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": []})
        
        self._postWithSyncToken("case_create.xml", sync_log.get_id)
        self._testUpdate(sync_log.get_id, {"asdf": [],
                                           "IKA9G79J4HDSPJLG3ER2OHQUY": []})
    
    @run_with_all_restore_configs
    def testOwnUpdatesDontSync(self):
        case_id = "own_updates_dont_sync"
        self._createCaseStubs([case_id])
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        
        self.factory.create_or_update_case(
            CaseStructure(case_id=case_id, attrs={'update': {"greeting": "hello"}}),
        )
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        self.factory.create_or_update_case(
            CaseStructure(case_id=case_id, attrs={'owner_id': OTHER_USER_ID}),
        )
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

    @run_with_all_restore_configs
    def test_change_index_type(self):
        """
        Test that changing an index type updates the sync log
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # update the child's index (parent type)
        updated_type = "updated_type"
        child = CaseBlock(
            create=False, case_id=child_id, user_id=USER_ID, version=V2,
            index={index_id: (updated_type, parent_id)},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        parent_ref.referenced_type = updated_type
        self._testUpdate(self.sync_log.get_id, {parent_id: [],
                                                child_id: [parent_ref]})

    @run_with_all_restore_configs
    def test_change_index_id(self):
        """
        Test that changing an index ID updates the sync log
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()

        # update the child's index (parent id)
        updated_id = 'changed_index_id'
        self.factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            relationships=[CaseRelationship(
                CaseStructure(case_id=updated_id, attrs={'create': True}),
                relationship=index_id,
                related_type=PARENT_TYPE,
            )],
        ))
        parent_ref.referenced_id = updated_id
        self._testUpdate(self.sync_log.get_id, {parent_id: [], updated_id: [],
                                                child_id: [parent_ref]})

    @run_with_all_restore_configs
    def test_add_multiple_indices(self):
        """
        Test that adding multiple indices works as expected
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # add new index
        new_case_id = 'new_case_id'
        new_index_id = 'new_index_id'

        self.factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            relationships=[CaseRelationship(
                CaseStructure(case_id=new_case_id, attrs={'create': True}),
                relationship=new_index_id,
                related_type=PARENT_TYPE,
            )],
        ))
        new_index_ref = CommCareCaseIndex(identifier=new_index_id, referenced_type=PARENT_TYPE,
                                          referenced_id=new_case_id)

        self._testUpdate(self.sync_log.get_id, {parent_id: [], new_case_id: [],
                                                child_id: [parent_ref, new_index_ref]})

    @run_with_all_restore_configs
    def test_delete_only_index(self):
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # delete the first index
        child = CaseBlock(create=False, case_id=child_id, user_id=USER_ID, version=V2,
                          index={index_id: (PARENT_TYPE, "")},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        self._testUpdate(self.sync_log.get_id, {parent_id: [], child_id: []})

    @run_with_all_restore_configs
    def test_delete_one_of_multiple_indices(self):
        # make IDs both human readable and globally unique to this test
        uid = uuid.uuid4().hex
        child_id = 'child_id-{}'.format(uid)
        parent_id_1 = 'parent_id-{}'.format(uid)
        index_id_1 = 'parent_index_id-{}'.format(uid)
        parent_id_2 = 'parent_id_2-{}'.format(uid)
        index_id_2 = 'parent_index_id_2-{}'.format(uid)

        self.factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            attrs={'create': True},
            relationships=[
                CaseRelationship(
                    CaseStructure(case_id=parent_id_1, attrs={'create': True}),
                    relationship=index_id_1,
                    related_type=PARENT_TYPE,
                ),
                CaseRelationship(
                    CaseStructure(case_id=parent_id_2, attrs={'create': True}),
                    relationship=index_id_2,
                    related_type=PARENT_TYPE,
                ),
            ],
        ))
        parent_ref_1 = CommCareCaseIndex(
            identifier=index_id_1, referenced_type=PARENT_TYPE, referenced_id=parent_id_1)
        parent_ref_2 = CommCareCaseIndex(
            identifier=index_id_2, referenced_type=PARENT_TYPE, referenced_id=parent_id_2)
        self._testUpdate(self.sync_log.get_id, {parent_id_1: [], parent_id_2: [],
                                                child_id: [parent_ref_1, parent_ref_2]})

        # delete the first index
        child = CaseBlock(create=False, case_id=child_id, user_id=USER_ID, version=V2,
                          index={index_id_1: (PARENT_TYPE, "")},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        self._testUpdate(self.sync_log.get_id, {parent_id_1: [], parent_id_2: [],
                                                child_id: [parent_ref_2]})

    def _initialize_parent_child(self):
        child_id = "child_id"
        parent_id = "parent_id"
        index_id = 'parent_index_id'
        self.factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            attrs={'create': True},
            relationships=[CaseRelationship(
                CaseStructure(case_id=parent_id, attrs={'create': True}),
                relationship=index_id,
                related_type=PARENT_TYPE,
            )],
        ))
        parent_ref = CommCareCaseIndex(identifier=index_id, referenced_type=PARENT_TYPE, referenced_id=parent_id)
        self._testUpdate(self.sync_log.get_id, {parent_id: [], child_id: [parent_ref]})
        return (child_id, parent_id, index_id, parent_ref)

    @run_with_all_restore_configs
    def testClosedParentIndex(self):
        """
        Tests that things work properly when you have a reference to the parent
        case in a child, even if it's closed.
        """
        parent_id = "mommy"
        child_id = "baby"
        index_id = 'my_mom_is'
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                relationships=[CaseRelationship(
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship=index_id,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
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
        assert_user_has_cases(self, self.user, [parent_id, child_id])

    @run_with_all_restore_configs
    def testAssignToNewOwner(self):
        # create parent and child
        parent_id = "mommy"
        child_id = "baby"
        index_id = 'my_mom_is'
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                relationships=[CaseRelationship(
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship=index_id,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
        index_ref = CommCareCaseIndex(identifier=index_id,
                                      referenced_type=PARENT_TYPE,
                                      referenced_id=parent_id)
        # should be there
        self._testUpdate(self.sync_log.get_id, {parent_id: [],
                                                child_id: [index_ref]})
        
        # assign the child to a new owner
        new_owner = "not_mine"
        self._postFakeWithSyncToken(
            CaseBlock(create=False, case_id=child_id, user_id=USER_ID, version=V2,
                      owner_id=new_owner
        ).as_xml(), self.sync_log.get_id)
        
        # child should be moved, parent should still be there
        self._testUpdate(self.sync_log.get_id, {parent_id: []}, {})

    @run_with_all_restore_configs
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
        form, _ = self._postFakeWithSyncToken(update_block, self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        form.archive()
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id, purge_restore_cache=True)

    @run_with_all_restore_configs
    def testUserLoggedIntoMultipleDevices(self):
        # test that a child case created by the same user from a different device
        # gets included in the sync

        parent_id = "parent"
        child_id = "child"
        self._createCaseStubs([parent_id])

        # create child case using a different sync log ID
        other_sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.user, version="2.0")
        )
        child = CaseBlock(
            create=True,
            case_id=child_id,
            user_id=USER_ID,
            owner_id=USER_ID,
            version=V2,
            index={'mother': ('mother', parent_id)}
        ).as_xml()
        self._postFakeWithSyncToken(child, other_sync_log.get_id)

        # ensure child case is included in sync using original sync log ID
        assert_user_has_case(self, self.user, child_id, restore_id=self.sync_log.get_id)

    @run_with_all_restore_configs
    def test_tiered_parent_closing(self):
        all_ids = [uuid.uuid4().hex for i in range(3)]
        [grandparent_id, parent_id, child_id] = all_ids
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                relationships=[CaseRelationship(
                    CaseStructure(
                        case_id=parent_id,
                        attrs={'create': True},
                        relationships=[CaseRelationship(
                            CaseStructure(case_id=grandparent_id, attrs={'create': True}),
                            relationship=PARENT_TYPE,
                            related_type=PARENT_TYPE,
                        )],
                    ),
                    relationship=PARENT_TYPE,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
        self.factory.close_case(grandparent_id)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        for id in all_ids:
            self.assertTrue(sync_log.phone_is_holding_case(id))

        self.factory.close_case(parent_id)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        for id in all_ids:
            self.assertTrue(sync_log.phone_is_holding_case(id))

        self.factory.close_case(child_id)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        for id in all_ids:
            # once the child is closed, all three are no longer relevant
            self.assertFalse(sync_log.phone_is_holding_case(id))

    @run_with_all_restore_configs
    def test_create_immediately_irrelevant_parent_case(self):
        """
        Make a case that is only relevant through a dependency at the same
        time as the dependency is made. Make sure it is relevant.
        """
        # create a parent and child case (with index) from one user
        parent_id, child_id = [uuid.uuid4().hex for i in range(2)]
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                relationships=[CaseRelationship(
                    CaseStructure(case_id=parent_id, attrs={'create': True, 'owner_id': uuid.uuid4().hex}),
                    relationship=PARENT_TYPE,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
        index_ref = CommCareCaseIndex(identifier=PARENT_TYPE,
                                      referenced_type=PARENT_TYPE,
                                      referenced_id=parent_id)
        self._testUpdate(self.sync_log._id, {child_id: [index_ref]}, {parent_id: []})
        self.clean = False


class SyncTokenCachingTest(SyncBaseTest):

    @run_with_all_restore_configs
    def testCaching(self):
        self.assertFalse(self.sync_log.has_cached_payload(V2))
        # first request should populate the cache
        original_payload = RestoreConfig(
            project=self.project,
            user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            )
        ).get_payload().as_string()
        next_sync_log = synclog_from_restore_payload(original_payload)

        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(self.sync_log.has_cached_payload(V2))

        # a second request with the same config should be exactly the same
        cached_payload = RestoreConfig(
            project=self.project,
            user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            )
        ).get_payload().as_string()
        self.assertEqual(original_payload, cached_payload)

        # caching a different version should also produce something new
        versioned_payload = RestoreConfig(
            project=self.project,
            user=self.user,
            params=RestoreParams(
                version=V1,
                sync_log_id=self.sync_log._id,
            ),
        ).get_payload().as_string()
        self.assertNotEqual(original_payload, versioned_payload)
        versioned_sync_log = synclog_from_restore_payload(versioned_payload)
        self.assertNotEqual(next_sync_log._id, versioned_sync_log._id)

    @run_with_all_restore_configs
    def test_initial_cache(self):
        restore_config = RestoreConfig(
            project=self.project,
            user=self.user,
            cache_settings=RestoreCacheSettings(force_cache=True),
        )
        original_payload = restore_config.get_payload()
        self.assertNotIsInstance(original_payload, CachedResponse)

        restore_config = RestoreConfig(project=self.project, user=self.user)
        cached_payload = restore_config.get_payload()
        self.assertIsInstance(cached_payload, CachedResponse)

        self.assertEqual(original_payload.as_string(), cached_payload.as_string())

    @run_with_all_restore_configs
    def testCacheInvalidation(self):
        original_payload = RestoreConfig(
            project=self.project,
            user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
        ).get_payload().as_string()
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(self.sync_log.has_cached_payload(V2))

        # posting a case associated with this sync token should invalidate the cache
        case_id = "cache_invalidation"
        self._createCaseStubs([case_id])
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertFalse(self.sync_log.has_cached_payload(V2))

        # resyncing should recreate the cache
        next_payload = RestoreConfig(
            project=self.project,
            user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
        ).get_payload().as_string()
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(self.sync_log.has_cached_payload(V2))
        self.assertNotEqual(original_payload, next_payload)
        self.assertFalse(case_id in original_payload)
        # since it was our own update, it shouldn't be in the new payload either
        self.assertFalse(case_id in next_payload)
        # we can be explicit about why this is the case
        self.assertTrue(self.sync_log.phone_is_holding_case(case_id))

    @run_with_all_restore_configs
    def testCacheNonInvalidation(self):
        original_payload = RestoreConfig(
            project=self.project,
            user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
        ).get_payload().as_string()
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(self.sync_log.has_cached_payload(V2))

        # posting a case associated with this sync token should invalidate the cache
        # submitting a case not with the token will not touch the cache for that token
        case_id = "cache_noninvalidation"
        post_case_blocks([CaseBlock(
            create=True,
            case_id=case_id,
            user_id=self.user.user_id,
            owner_id=self.user.user_id,
            case_type=PARENT_TYPE,
            version=V2,
        ).as_xml()])
        next_payload = RestoreConfig(
            project=self.project,
            user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
        ).get_payload().as_string()
        self.assertEqual(original_payload, next_payload)
        self.assertFalse(case_id in next_payload)

    @run_with_all_restore_configs
    def testCacheInvalidationAfterFileDelete(self):
        # first request should populate the cache
        original_payload = RestoreConfig(
            project=self.project,
            user=self.user,
            cache_settings=RestoreCacheSettings(force_cache=True)
        ).get_payload()
        self.assertNotIsInstance(original_payload, CachedResponse)

        # Delete cached file
        os.remove(original_payload.get_filename())

        # resyncing should recreate the cache
        next_file = RestoreConfig(project=self.project, user=self.user).get_payload()
        self.assertNotIsInstance(next_file, CachedResponse)
        self.assertNotEqual(original_payload.get_filename(), next_file.get_filename())


class MultiUserSyncTest(SyncBaseTest):
    """
    Tests the interaction of two users in sync mode doing various things
    """

    def setUp(self):
        super(MultiUserSyncTest, self).setUp()
        # the other user is an "owner" of the original users cases as well,
        # for convenience
        self.other_user = User(user_id=OTHER_USER_ID, username=OTHER_USERNAME,
                               password="changeme", date_joined=datetime(2011, 6, 9),
                               additional_owner_ids=[SHARED_ID])
        
        # this creates the initial blank sync token in the database
        self.other_sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.other_user)
        )
        
        self.assertTrue(SHARED_ID in self.other_sync_log.owner_ids_on_phone)
        self.assertTrue(OTHER_USER_ID in self.other_sync_log.owner_ids_on_phone)
        
        self.user.additional_owner_ids = [SHARED_ID]
        self.sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.user)
        )
        self.assertTrue(SHARED_ID in self.sync_log.owner_ids_on_phone)
        self.assertTrue(USER_ID in self.sync_log.owner_ids_on_phone)
        # since we got a new sync log, have to update the factory as well
        self.factory.form_extras = {'last_sync_token': self.sync_log._id}
        self.factory.case_defaults.update({'owner_id': SHARED_ID})

    @run_with_all_restore_configs
    def testSharedCase(self):
        # create a case by one user
        case_id = "shared_case"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)
        # should sync to the other owner
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)
        
    @run_with_all_restore_configs
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
        _, match = assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        self.assertTrue("Hello!" in match.to_string())

    @run_with_all_restore_configs
    def testOtherUserAddsIndex(self):
        time = datetime.utcnow()

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
        _, orig = assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        self.assertTrue("index" in orig.to_string())

    @run_with_all_restore_configs
    def testMultiUserEdits(self):
        time = datetime.utcnow()

        # create a case from one user
        case_id = "multi_user_edits"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)

        # both users syncs
        main_sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.user)
        )
        self.other_sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.other_user)
        )

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
            main_sync_log.get_id
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

        check_user_has_case(self, self.user, joint_change, restore_id=main_sync_log.get_id, version=V2)
        check_user_has_case(self, self.other_user, joint_change, restore_id=self.other_sync_log.get_id, version=V2)

    @run_with_all_restore_configs
    def testOtherUserCloses(self):
        # create a case from one user
        case_id = "other_user_closes"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)

        # sync then close case from another user
        other_sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.other_user)
        )
        close_block = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            version=V2,
            close=True
        ).as_xml()
        self._postFakeWithSyncToken(
            close_block,
            other_sync_log.get_id
        )

        # original user syncs again
        # make sure close block appears
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

    @run_with_all_restore_configs
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

    @run_with_all_restore_configs
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

    @run_with_all_restore_configs
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
        
        main_sync_log = get_properly_wrapped_sync_log(self.sync_log.get_id)
        
        # these tests added to debug another issue revealed by this test
        self.assertTrue(main_sync_log.phone_is_holding_case(case_id))
        self.assertTrue(main_sync_log.phone_is_holding_case(parent_id))
        
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
        latest_sync_log = SyncLog.last_for_user(USER_ID)
        assert_user_has_case(self, self.user, parent_id, restore_id=latest_sync_log.get_id,
                             purge_restore_cache=True)

    @run_with_all_restore_configs
    def testOtherUserReassignsIndexed(self):
        # create a parent and child case (with index) from one user
        parent_id = "other_reassigns_index_parent"
        case_id = "other_reassigns_index_child"
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=case_id,
                attrs={'create': True},
                relationships=[CaseRelationship(
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship=PARENT_TYPE,
                    related_type=PARENT_TYPE,
                )],
            )
        ])

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
        other_sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.other_user)
        )

        # change the child's owner from another user
        child_reassignment = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=OTHER_USER_ID,
            owner_id=OTHER_USER_ID,
            version=V2,
            update={"childgreeting": "hi!"}, 
        ).as_xml()
        self._postFakeWithSyncToken(child_reassignment, other_sync_log.get_id)
        
        # also change the parent from the second user
        other_parent_update = CaseBlock(
            create=False, 
            case_id=parent_id,
            user_id=OTHER_USER_ID, 
            owner_id=OTHER_USER_ID,
            update={"other_greeting": "something new"}, 
            version=V2).as_xml()
        self._postFakeWithSyncToken(other_parent_update, other_sync_log.get_id)
        
        # original user syncs again
        latest_sync_log = SyncLog.last_for_user(self.user.user_id)
        # both cases should sync to original user with updated ownership / edits
        assert_user_has_case(self, self.user, case_id, restore_id=latest_sync_log.get_id)
        assert_user_has_case(self, self.user, parent_id, restore_id=latest_sync_log.get_id)

        # Ghetto
        payload = generate_restore_payload(self.project, self.user, latest_sync_log.get_id, version=V2)
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
        self._postFakeWithSyncToken(other_parent_update, other_sync_log.get_id)
        
        
        # original user syncs again
        latest_sync_log = SyncLog.last_for_user(self.user.user_id)
        # should be no changes
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=latest_sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, parent_id, restore_id=latest_sync_log.get_id)

        # change the child again from the second user
        other_child_update = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=OTHER_USER_ID,
            owner_id=OTHER_USER_ID,
            version=V2,
            update={"childgreeting": "hi changed!"}, 
        ).as_xml()
        self._postFakeWithSyncToken(other_child_update, other_sync_log.get_id)
        
        # original user syncs again
        latest_sync_log = SyncLog.last_for_user(self.user.user_id)
        # should be no changes
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=latest_sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, parent_id, restore_id=latest_sync_log.get_id)

        # change owner of child back to orginal user from second user
        child_reassignment = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=OTHER_USER_ID,
            owner_id=USER_ID,
            version=V2
        ).as_xml()
        self._postFakeWithSyncToken(child_reassignment, other_sync_log.get_id)
        
        # original user syncs again
        latest_sync_log = SyncLog.last_for_user(self.user.user_id)
        # both cases should now sync
        assert_user_has_case(self, self.user, case_id, restore_id=latest_sync_log.get_id)
        assert_user_has_case(self, self.user, parent_id, restore_id=latest_sync_log.get_id)

        # ghetto
        payload = generate_restore_payload(
            self.project, self.user, latest_sync_log.get_id, version=V2
        )
        self.assertTrue("something different" in payload)
        self.assertTrue("hi changed!" in payload)
    
    @run_with_all_restore_configs
    def testComplicatedGatesBug(self):
        # found this bug in the wild, used the real (test) forms to fix it
        # just running through this test used to fail hard, even though there
        # are no asserts
        folder_path = os.path.join("bugs", "dependent_case_conflicts")
        files = ["reg1.xml", "reg2.xml", "cf.xml", "close.xml"]
        for f in files:
            form = self._postWithSyncToken(os.path.join(folder_path, f), self.sync_log.get_id)
            form = XFormInstance.get(form.get_id)
            self.assertFalse(hasattr(form, "problem"))
            synclog_from_restore_payload(
                generate_restore_payload(self.project, self.user, version="2.0")
            )

    @run_with_all_restore_configs
    def test_dependent_case_becomes_relevant_at_sync_time(self):
        """
        Make a case that is only relevant through a dependency.
        Then update it to be actually relevant.
        Make sure the sync removes it from the dependent list.
        """
        # create a parent and child case (with index) from one user
        parent_id, child_id = [uuid.uuid4().hex for i in range(2)]
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                relationships=[CaseRelationship(
                    CaseStructure(case_id=parent_id, attrs={'create': True, 'owner_id': uuid.uuid4().hex}),
                    relationship=PARENT_TYPE,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
        index_ref = CommCareCaseIndex(identifier=PARENT_TYPE,
                                      referenced_type=PARENT_TYPE,
                                      referenced_id=parent_id)

        # sanity check that we are in the right state
        self._testUpdate(self.sync_log._id, {child_id: [index_ref]}, {parent_id: []})

        # have another user modify the owner ID of the dependent case to be the shared ID
        self.factory.create_or_update_cases(
            [
                CaseStructure(
                    case_id=parent_id,
                    attrs={'owner_id': SHARED_ID},
                )
            ],
            form_extras={'last_sync_token': None}
        )
        latest_sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.user, restore_id=self.sync_log._id)
        )
        self._testUpdate(latest_sync_log._id, {child_id: [index_ref], parent_id: []})

    @run_with_all_restore_configs
    def test_index_tree_conflict_handling(self):
        """
        Test that if another user changes the index tree, the original user
        gets the appropriate index tree update after sync.
        """
        # create a parent and child case (with index) from one user
        mom_id, dad_id, child_id = [uuid.uuid4().hex for i in range(3)]
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                relationships=[
                    CaseRelationship(
                        CaseStructure(case_id=mom_id, attrs={'create': True}),
                        relationship='mom',
                        related_type='mom',
                    ),
                    CaseRelationship(
                        CaseStructure(case_id=dad_id, attrs={'create': True}),
                        relationship='dad',
                        related_type='dad',
                    ),

                ],
            )
        ])
        mom_ref = CommCareCaseIndex(identifier='mom', referenced_type='mom', referenced_id=mom_id)
        dad_ref = CommCareCaseIndex(identifier='dad', referenced_type='dad', referenced_id=dad_id)
        # sanity check that we are in the right state
        self._testUpdate(self.sync_log._id, {child_id: [mom_ref, dad_ref], mom_id: [], dad_id: []})

        # have another user modify the index ID of one of the cases
        new_mom_id = uuid.uuid4().hex
        self.factory.create_or_update_cases(
            [
                CaseStructure(
                    case_id=child_id,
                    relationships=[
                        CaseRelationship(
                            CaseStructure(case_id=new_mom_id, attrs={'create': True}),
                            relationship='mom',
                            related_type='mom',
                        ),
                    ]
                )
            ],
            form_extras={'last_sync_token': None}
        )
        latest_sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.user, restore_id=self.sync_log._id)
        )
        new_mom_ref = CommCareCaseIndex(identifier='mom', referenced_type='mom', referenced_id=new_mom_id)
        self._testUpdate(latest_sync_log._id, {
            child_id: [new_mom_ref, dad_ref], mom_id: [], dad_id: [], new_mom_id: []
        })


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
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        cases_on_phone = sync_log.tests_only_get_cases_on_phone()
        self.assertEqual(1, len(cases_on_phone))
        self.assertEqual(case_id, cases_on_phone[0].case_id)

        # manually delete it and then try to update
        sync_log.test_only_clear_cases_on_phone()
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
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
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


class LooseSyncTokenValidationTest(SyncBaseTest):

    def test_submission_with_bad_log_default(self):
        with self.assertRaises(ResourceNotFound):
            post_case_blocks(
                [CaseBlock(create=True, case_id='bad-log-default', version=V2).as_xml()],
                form_extras={"last_sync_token": 'not-a-valid-synclog-id'},
                domain='some-domain-without-toggle',
            )

    def test_submission_with_bad_log_toggle_enabled(self):
        domain = 'submission-domain-with-toggle'

        def _test():
            post_case_blocks(
                [CaseBlock(create=True, case_id='bad-log-toggle-enabled', version=V2).as_xml()],
                form_extras={"last_sync_token": 'not-a-valid-synclog-id'},
                domain=domain,
            )

        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, False, namespace='domain')
        with self.assertRaises(ResourceNotFound):
            _test()

        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, True, namespace='domain')
        # this is just asserting that an exception is not raised after the toggle is set
        _test()

    def test_restore_with_bad_log_default(self):
        with self.assertRaises(MissingSyncLog):
            RestoreConfig(
                project=Domain(name="test_restore_with_bad_log_default"),
                user=self.user,
                params=RestoreParams(
                    version=V2,
                    sync_log_id='not-a-valid-synclog-id',
                ),
            ).get_payload()

    def test_restore_with_bad_log_toggle_enabled(self):
        domain = 'restore-domain-with-toggle'

        def _test():
            RestoreConfig(
                project=Domain(name=domain),
                user=self.user,
                params=RestoreParams(
                    version=V2,
                    sync_log_id='not-a-valid-synclog-id',
                )
            ).get_payload()

        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, False, namespace='domain')
        with self.assertRaises(MissingSyncLog):
            _test()

        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, True, namespace='domain')
        # when the toggle is set the exception should be a RestoreException instead
        with self.assertRaises(RestoreException):
            _test()
