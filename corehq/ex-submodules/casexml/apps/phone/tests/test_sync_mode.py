import uuid
from xml.etree import ElementTree
from couchdbkit import ResourceNotFound
from django.test.utils import override_settings
from django.test import TestCase
import os

from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.exceptions import MissingSyncLog, RestoreException
from casexml.apps.phone.tests.utils import get_exactly_one_wrapped_sync_log, generate_restore_payload
from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure, CaseIndex
from casexml.apps.phone.tests.utils import synclog_from_restore_payload, get_restore_config
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils, \
    run_with_all_backends
from corehq.toggles import LOOSE_SYNC_TOKEN_VALIDATION
from corehq.util.test_utils import flag_enabled
from casexml.apps.case.tests.util import (
    check_user_has_case, assert_user_doesnt_have_case,
    assert_user_has_case, TEST_DOMAIN_NAME, assert_user_has_cases)
from casexml.apps.phone.models import SyncLog, User, get_properly_wrapped_sync_log, SimplifiedSyncLog, \
    AbstractSyncLog
from casexml.apps.phone.restore import CachedResponse, RestoreConfig, RestoreParams, RestoreCacheSettings
from casexml.apps.case.xml import V2, V1
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from datetime import datetime

USER_ID = "main_user"
USERNAME = "syncguy"
OTHER_USER_ID = "someone_else"
OTHER_USERNAME = "ferrel"
SHARED_ID = "our_group"
PARENT_TYPE = "mother"
CHILD_RELATIONSHIP = "child"

@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class SyncBaseTest(TestCase):
    """
    Shared functionality among tests
    """

    def setUp(self):
        FormProcessorTestUtils.delete_all_cases()
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_sync_logs()
        self.project = Domain(name=TEST_DOMAIN_NAME)
        self.user = User(user_id=USER_ID, username=USERNAME,
                         password="changeme", date_joined=datetime(2011, 6, 9))
        # this creates the initial blank sync token in the database
        restore_config = RestoreConfig(self.project, user=self.user,
                                       cache_settings=RestoreCacheSettings(overwrite_cache=True))
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
        _, form, _ = submit_form_locally(xml_data, 'test-domain', last_sync_token=token_id)
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
            self.assertEqual(sync_log.get_state_hash(), migrated_sync_log.get_state_hash())
            self._testUpdate(migrated_sync_log, case_id_map, dependent_case_id_map)


class SyncTokenUpdateTest(SyncBaseTest):
    """
    Tests sync token updates on submission related to the list of cases
    on the phone and the footprint.
    """

    @run_with_all_backends
    def testInitialEmpty(self):
        """
        Tests that a newly created sync token has no cases attached to it.
        """
        sync_log = get_exactly_one_wrapped_sync_log()
        self._testUpdate(sync_log.get_id, {}, {})

    @run_with_all_backends
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

    @run_with_all_backends
    def test_change_index_type(self):
        """
        Test that changing an index type updates the sync log
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # update the child's index (parent type)
        updated_type = "updated_type"
        child = CaseBlock(
            create=False, case_id=child_id, user_id=USER_ID,
            index={index_id: (updated_type, parent_id)},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        parent_ref.referenced_type = updated_type
        self._testUpdate(self.sync_log.get_id, {parent_id: [],
                                                child_id: [parent_ref]})

    @run_with_all_backends
    def test_change_index_id(self):
        """
        Test that changing an index ID updates the sync log
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()

        # update the child's index (parent id)
        updated_id = 'changed_index_id'
        self.factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            indices=[CaseIndex(
                CaseStructure(case_id=updated_id, attrs={'create': True}),
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
                identifier=index_id,
            )],
        ))
        parent_ref.referenced_id = updated_id
        self._testUpdate(self.sync_log.get_id, {parent_id: [], updated_id: [],
                                                child_id: [parent_ref]})

    @run_with_all_backends
    def test_add_multiple_indices(self):
        """
        Test that adding multiple indices works as expected
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # add new index
        new_case_id = 'new_case_id'
        new_index_identifier = 'new_index_id'

        self.factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            indices=[CaseIndex(
                CaseStructure(case_id=new_case_id, attrs={'create': True}),
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
                identifier=new_index_identifier,
            )],
        ))
        new_index_ref = CommCareCaseIndex(identifier=new_index_identifier, referenced_type=PARENT_TYPE,
                                          referenced_id=new_case_id)

        self._testUpdate(self.sync_log.get_id, {parent_id: [], new_case_id: [],
                                                child_id: [parent_ref, new_index_ref]})

    @run_with_all_backends
    def test_delete_only_index(self):
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # delete the first index
        child = CaseBlock(create=False, case_id=child_id, user_id=USER_ID,
                          index={index_id: (PARENT_TYPE, "")},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        self._testUpdate(self.sync_log.get_id, {parent_id: [], child_id: []})

    @run_with_all_backends
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
            indices=[
                CaseIndex(
                    CaseStructure(case_id=parent_id_1, attrs={'create': True}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                    identifier=index_id_1,
                ),
                CaseIndex(
                    CaseStructure(case_id=parent_id_2, attrs={'create': True}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                    identifier=index_id_2,
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
        child = CaseBlock(create=False, case_id=child_id, user_id=USER_ID,
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
            indices=[CaseIndex(
                CaseStructure(case_id=parent_id, attrs={'create': True}),
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
                identifier=index_id,
            )],
        ))
        parent_ref = CommCareCaseIndex(identifier=index_id, referenced_type=PARENT_TYPE, referenced_id=parent_id)
        self._testUpdate(self.sync_log.get_id, {parent_id: [], child_id: [parent_ref]})
        return (child_id, parent_id, index_id, parent_ref)

    @run_with_all_backends
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
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                    identifier=index_id,
                )],
            )
        ])
        index_ref = CommCareCaseIndex(identifier=index_id,
                                      referenced_type=PARENT_TYPE,
                                      referenced_id=parent_id)

        self._testUpdate(self.sync_log.get_id, {parent_id: [],
                                                child_id: [index_ref]})

        # close the mother case
        close = CaseBlock(create=False, case_id=parent_id, user_id=USER_ID, close=True).as_xml()
        self._postFakeWithSyncToken(close, self.sync_log.get_id)
        self._testUpdate(self.sync_log.get_id, {child_id: [index_ref]},
                         {parent_id: []})

        # try a clean restore again
        assert_user_has_cases(self, self.user, [parent_id, child_id])

    @run_with_all_backends
    def testAssignToNewOwner(self):
        # create parent and child
        parent_id = "mommy"
        child_id = "baby"
        index_id = 'my_mom_is'
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                    identifier=index_id,
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
            CaseBlock(create=False, case_id=child_id, user_id=USER_ID, owner_id=new_owner).as_xml(),
            self.sync_log.get_id
        )

        # child should be moved, parent should still be there
        self._testUpdate(self.sync_log.get_id, {parent_id: []}, {})

    @run_with_all_backends
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
            update={"greeting": "hello"}
        ).as_xml()
        form, _ = self._postFakeWithSyncToken(update_block, self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        form.archive()
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id, purge_restore_cache=True)

    @run_with_all_backends
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
            index={'mother': ('mother', parent_id)}
        ).as_xml()
        self._postFakeWithSyncToken(child, other_sync_log.get_id)

        # ensure child case is included in sync using original sync log ID
        assert_user_has_case(self, self.user, child_id, restore_id=self.sync_log.get_id)

    @run_with_all_backends
    def test_tiered_parent_closing(self):
        all_ids = [uuid.uuid4().hex for i in range(3)]
        [grandparent_id, parent_id, child_id] = all_ids
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(
                        case_id=parent_id,
                        attrs={'create': True},
                        indices=[CaseIndex(
                            CaseStructure(case_id=grandparent_id, attrs={'create': True}),
                            relationship=CHILD_RELATIONSHIP,
                            related_type=PARENT_TYPE,
                        )],
                    ),
                    relationship=CHILD_RELATIONSHIP,
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

    @run_with_all_backends
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
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={'create': True, 'owner_id': uuid.uuid4().hex}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                    identifier=PARENT_TYPE,
                )],
            )
        ])
        index_ref = CommCareCaseIndex(identifier=PARENT_TYPE,
                                      referenced_type=PARENT_TYPE,
                                      referenced_id=parent_id)
        self._testUpdate(self.sync_log._id, {child_id: [index_ref]}, {parent_id: []})

    @run_with_all_backends
    def test_closed_case_not_in_next_sync(self):
        # create a case
        case_id = self.factory.create_case().case_id
        # sync
        restore_config = RestoreConfig(
            project=Domain(name=self.project.name),
            user=self.user, params=RestoreParams(self.sync_log._id, version=V2)
        )
        next_sync = synclog_from_restore_payload(restore_config.get_payload().as_string())
        self.assertTrue(next_sync.phone_is_holding_case(case_id))
        # close the case on the second sync
        self.factory.create_or_update_case(CaseStructure(case_id=case_id, attrs={'close': True}),
                                           form_extras={'last_sync_token': next_sync._id})
        # sync again
        restore_config = RestoreConfig(
            project=Domain(name=self.project.name),
            user=self.user, params=RestoreParams(next_sync._id, version=V2)
        )
        last_sync = synclog_from_restore_payload(restore_config.get_payload().as_string())
        self.assertFalse(last_sync.phone_is_holding_case(case_id))

    @run_with_all_backends
    def test_sync_by_user_id(self):
        # create a case with an empty owner but valid user id
        case_id = self.factory.create_case(owner_id='', user_id=USER_ID).case_id
        restore_config = RestoreConfig(self.project, user=self.user)
        payload = restore_config.get_payload().as_string()
        self.assertTrue(case_id in payload)
        sync_log = synclog_from_restore_payload(payload)
        self.assertTrue(sync_log.phone_is_holding_case(case_id))

    @run_with_all_backends
    def test_create_irrelevant_owner_and_update_to_irrelevant_owner_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        self.factory.create_case(owner_id='irrelevant_1', update={'owner_id': 'irrelevant_2'}, strict=False)

    @run_with_all_backends
    def test_create_irrelevant_owner_and_update_to_relevant_owner_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        case = self.factory.create_case(owner_id='irrelevant_1', update={'owner_id': USER_ID}, strict=False)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        # todo: this bug isn't fixed on old sync. This check is a hack due to the inability to
        # override the setting on a per-test level and should be removed when the new
        # sync is fully rolled out.
        if isinstance(sync_log, SimplifiedSyncLog):
            self.assertTrue(sync_log.phone_is_holding_case(case.case_id))

    @run_with_all_backends
    def test_create_relevant_owner_and_update_to_empty_owner_in_same_form(self):
        case = self.factory.create_case(owner_id=USER_ID, update={'owner_id': ''}, strict=False)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        if isinstance(sync_log, SimplifiedSyncLog):
            self.assertFalse(sync_log.phone_is_holding_case(case.case_id))

    @run_with_all_backends
    def test_create_irrelevant_owner_and_update_to_empty_owner_in_same_form(self):
        case = self.factory.create_case(owner_id='irrelevant_1', update={'owner_id': ''}, strict=False)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertFalse(sync_log.phone_is_holding_case(case.case_id))

    @run_with_all_backends
    def test_create_relevant_owner_then_submit_again_with_no_owner(self):
        case = self.factory.create_case()
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(sync_log.phone_is_holding_case(case.case_id))
        self.factory.create_or_update_case(CaseStructure(
            case_id=case.case_id,
            attrs={'owner_id': None}
        ))
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(sync_log.phone_is_holding_case(case.case_id))

    @run_with_all_backends
    def test_create_irrelevant_owner_then_submit_again_with_no_owner(self):
        case = self.factory.create_case(owner_id='irrelevant_1')
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertFalse(sync_log.phone_is_holding_case(case.case_id))
        self.factory.create_or_update_case(CaseStructure(
            case_id=case.case_id,
            attrs={'owner_id': None}
        ))
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertFalse(sync_log.phone_is_holding_case(case.case_id))

    @run_with_all_backends
    def test_create_irrelevant_child_case_and_close_parent_in_same_form(self):
        # create the parent
        parent_id = self.factory.create_case().case_id
        # create an irrelevent child and close the parent
        child_id = uuid.uuid4().hex
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={
                    'create': True,
                    'owner_id': 'irrelevant_1',
                    'update': {'owner_id': 'irrelevant_2'},
                    'strict': False
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={'close': True}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
        # they should both be gone
        self._testUpdate(self.sync_log._id, {}, {})

    @run_with_all_backends
    def test_create_closed_child_case_and_close_parent_in_same_form(self):
        # create the parent
        parent_id = self.factory.create_case().case_id
        # create an irrelevent child and close the parent
        child_id = uuid.uuid4().hex
        self.factory.create_or_update_cases([
            CaseStructure(case_id=parent_id, attrs={'close': True, 'owner_id': CaseBlock.undefined}),
            CaseStructure(
                case_id=child_id,
                attrs={
                    'create': True,
                    'close': True,
                    'update': {'foo': 'bar'},
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                )],
                walk_related=False,
            )
        ])
        # they should both be gone
        self._testUpdate(self.sync_log._id, {}, {})

    @run_with_all_backends
    def test_create_irrelevant_owner_and_close_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        self.factory.create_case(owner_id='irrelevant_1', close=True)

    @run_with_all_backends
    def test_reassign_and_close_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        case_id = self.factory.create_case().case_id
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=case_id,
                attrs={'owner_id': 'irrelevant', 'close': True},
            )
        )

    @run_with_all_backends
    def test_index_after_close(self):
        parent_id = self.factory.create_case().case_id
        case_id = uuid.uuid4().hex
        case_xml = self.factory.get_case_block(case_id, create=True, close=True)
        # hackily insert an <index> block after the close
        index_wrapper = ElementTree.Element('index')
        index_elem = ElementTree.Element('parent')
        index_elem.set('case_type', 'test')
        index_elem.set('relationship', 'child')
        index_elem.text = parent_id
        index_wrapper.append(index_elem)
        case_xml.append(index_wrapper)
        self.factory.post_case_blocks([case_xml])
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        # before this test was written, the case stayed on the sync log even though it was closed
        self.assertFalse(sync_log.phone_is_holding_case(case_id))

    @run_with_all_backends
    def test_index_chain_with_closed_parents(self):
        grandparent = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'close': True}
        )
        parent = CaseStructure(
            case_id=uuid.uuid4().hex,
            attrs={'close': True},
            indices=[CaseIndex(
                grandparent,
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
            )]
        )
        child = CaseStructure(
            case_id=uuid.uuid4().hex,
            indices=[CaseIndex(
                parent,
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
            )]
        )
        parent_ref = CommCareCaseIndex(
            identifier=PARENT_TYPE,
            referenced_type=PARENT_TYPE,
            referenced_id=parent.case_id)
        grandparent_ref = CommCareCaseIndex(
            identifier=PARENT_TYPE,
            referenced_type=PARENT_TYPE,
            referenced_id=grandparent.case_id)

        self.factory.create_or_update_cases([child])

        self._testUpdate(
            self.sync_log._id,
            {child.case_id: [parent_ref],
             parent.case_id: [grandparent_ref],
             grandparent.case_id: []},
            {parent.case_id: [grandparent.case_id],
             grandparent.case_id: []}
        )

    @run_with_all_backends
    def test_reassign_case_and_sync(self):
        case = self.factory.create_case()
        # reassign from an empty sync token, simulating a web-reassignment on HQ
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=case.case_id,
                attrs={'owner_id': 'irrelevant'},
            ),
            form_extras={'last_sync_token': None}
        )
        assert_user_has_case(self, self.user, case.case_id, restore_id=self.sync_log._id)
        payload = generate_restore_payload(self.project, self.user, restore_id=self.sync_log._id, version=V2)
        next_sync_log = synclog_from_restore_payload(payload)
        self.assertFalse(next_sync_log.phone_is_holding_case(case.case_id))

    @run_with_all_backends
    def test_cousins(self):
        """http://manage.dimagi.com/default.asp?189528
        """
        other_owner_id = uuid.uuid4().hex
        grandparent = CaseStructure(
            case_id="Steffon",
            attrs={'owner_id': other_owner_id}
        )
        parent_1 = CaseStructure(
            case_id="Stannis",
            attrs={'owner_id': other_owner_id},
            indices=[CaseIndex(grandparent)]
        )
        parent_2 = CaseStructure(
            case_id="Robert",
            attrs={'owner_id': other_owner_id},
            indices=[CaseIndex(grandparent)]
        )
        child_1 = CaseStructure(
            case_id="Shireen",
            indices=[CaseIndex(parent_1)]
        )
        child_2 = CaseStructure(
            case_id="Joffrey",
            indices=[CaseIndex(parent_2)]
        )
        self.factory.create_or_update_cases([grandparent, parent_1, parent_2, child_1, child_2])
        assert_user_has_cases(self, self.user, [
            grandparent.case_id,
            parent_1.case_id,
            parent_2.case_id,
            child_1.case_id,
            child_2.case_id
        ])


class SyncDeletedCasesTest(SyncBaseTest):

    @run_with_all_backends
    def test_deleted_case_doesnt_sync(self):
        case = self.factory.create_case()
        case.soft_delete()
        assert_user_doesnt_have_case(self, self.user, case.case_id)

    @run_with_all_backends
    def test_deleted_parent_doesnt_sync(self):
        parent_id = uuid.uuid4().hex
        child_id = uuid.uuid4().hex
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=child_id,
                attrs={
                    'create': True,
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
        CaseAccessors().get_case(parent_id).soft_delete()
        assert_user_doesnt_have_case(self, self.user, parent_id)
        # todo: in the future we may also want to purge the child
        assert_user_has_case(self, self.user, child_id)


class ExtensionCasesSyncTokenUpdates(SyncBaseTest):
    """Makes sure the extension case trees are propertly updated
    """

    @run_with_all_backends
    def test_create_extension(self):
        """creating an extension should add it to the extension_index_tree
        """
        case_type = 'case'
        index_identifier = 'idx'
        host = CaseStructure(case_id='host',
                             attrs={'create': True})
        extension = CaseStructure(
            case_id='extension',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                host,
                identifier=index_identifier,
                relationship='extension',
                related_type=case_type,
            )],
        )

        self.factory.create_or_update_cases([extension])
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertDictEqual(sync_log.index_tree.indices, {})
        self.assertDictEqual(sync_log.extension_index_tree.indices,
                             {extension.case_id: {index_identifier: host.case_id}})
        self.assertEqual(sync_log.dependent_case_ids_on_phone, set([extension.case_id]))
        self.assertEqual(sync_log.case_ids_on_phone, set([extension.case_id, host.case_id]))

    @run_with_all_backends
    def test_create_multiple_indices(self):
        """creating multiple indices should add to the right tree
        """
        case_type = 'case'
        host = CaseStructure(case_id='host',
                             attrs={'create': True})
        extension = CaseStructure(
            case_id='extension',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                host,
                identifier='host',
                relationship='extension',
                related_type=case_type,
            ), CaseIndex(
                CaseStructure(case_id=host.case_id, attrs={'create': False}),
                identifier='child',
                relationship='child',
                related_type=case_type,
            )],
        )

        self.factory.create_or_update_cases([extension])
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertDictEqual(sync_log.index_tree.indices,
                             {extension.case_id: {'child': host.case_id}})
        self.assertDictEqual(sync_log.extension_index_tree.indices,
                             {extension.case_id: {'host': host.case_id}})

    @run_with_all_backends
    def test_create_extension_with_extension(self):
        """creating multiple extensions should be added to the right tree
        """
        case_type = 'case'
        host = CaseStructure(case_id='host',
                             attrs={'create': True})
        extension = CaseStructure(
            case_id='extension',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                host,
                identifier='host',
                relationship='extension',
                related_type=case_type,
            )],
        )
        extension_extension = CaseStructure(
            case_id='extension_extension',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                extension,
                identifier='host_2',
                relationship='extension',
                related_type=case_type,
            )]
        )

        self.factory.create_or_update_cases([extension_extension])
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        expected_extension_tree = {extension.case_id: {'host': host.case_id},
                                   extension_extension.case_id: {'host_2': extension.case_id}}
        self.assertDictEqual(sync_log.index_tree.indices, {})
        self.assertDictEqual(sync_log.extension_index_tree.indices, expected_extension_tree)

    @run_with_all_backends
    def test_create_extension_then_delegate(self):
        """A delegated extension should still remain on the phone with the host
        """
        case_type = 'case'
        host = CaseStructure(case_id='host',
                             attrs={'create': True})
        extension = CaseStructure(
            case_id='extension',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                host,
                identifier='host',
                relationship='extension',
                related_type=case_type,
            )],
        )
        self.factory.create_or_update_case(extension)

        delegated_extension = CaseStructure(case_id=extension.case_id, attrs={'owner_id': 'me'})
        self.factory.create_or_update_case(delegated_extension)

        expected_extension_tree = {extension.case_id: {'host': host.case_id}}
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertDictEqual(sync_log.extension_index_tree.indices, expected_extension_tree)
        self.assertEqual(sync_log.dependent_case_ids_on_phone, set([extension.case_id]))
        self.assertEqual(sync_log.case_ids_on_phone, set([extension.case_id, host.case_id]))

    @run_with_all_backends
    def test_create_delegated_extension(self):
        case_type = 'case'
        host = CaseStructure(case_id='host',
                             attrs={'create': True})
        extension = CaseStructure(
            case_id='extension',
            attrs={'create': True, 'owner_id': 'foobar'},
            indices=[CaseIndex(
                host,
                identifier='host',
                relationship='extension',
                related_type=case_type,
            )],
        )
        self.factory.create_or_update_case(extension)

        expected_extension_tree = {extension.case_id: {'host': host.case_id}}
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertDictEqual(sync_log.extension_index_tree.indices, expected_extension_tree)
        self.assertEqual(sync_log.case_ids_on_phone, set([host.case_id, extension.case_id]))

    @run_with_all_backends
    def test_close_host(self):
        """closing a host should update the appropriate trees
        """
        case_type = 'case'
        index_identifier = 'idx'
        host = CaseStructure(case_id='host',
                             attrs={'create': True})
        extension = CaseStructure(
            case_id='extension',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                host,
                identifier=index_identifier,
                relationship='extension',
                related_type=case_type,
            )],
        )

        self.factory.create_or_update_cases([extension])
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertDictEqual(sync_log.extension_index_tree.indices,
                             {extension.case_id: {index_identifier: host.case_id}})

        closed_host = CaseStructure(case_id=host.case_id, attrs={'close': True})
        self.factory.create_or_update_case(closed_host)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertDictEqual(sync_log.extension_index_tree.indices, {})
        self.assertEqual(sync_log.dependent_case_ids_on_phone, set([]))
        self.assertEqual(sync_log.case_ids_on_phone, set([]))

    @run_with_all_backends
    def test_long_chain_with_children(self):
        """
                  +----+
                  | E1 |
                  +--^-+
                     |e
        +---+     +--+-+
        |O  +--c->| C  |
        +---+     +--^-+
       (owned)       |e
                  +--+-+
                  | E2 |
                  +----+
        """
        case_type = 'case'

        E1 = CaseStructure(
            case_id='extension_1',
            attrs={'create': True, 'owner_id': '-'},
        )

        C = CaseStructure(
            case_id='child',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                E1,
                identifier='extension_1',
                relationship='extension',
                related_type=case_type,
            )]
        )

        O = CaseStructure(
            case_id='owned',
            attrs={'create': True},
            indices=[CaseIndex(
                C,
                identifier='child',
                relationship='child',
                related_type=case_type,
            )]
        )
        E2 = CaseStructure(
            case_id='extension_2',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                C,
                identifier='extension',
                relationship='extension',
                related_type=case_type,
            )]
        )
        self.factory.create_or_update_cases([O, E2])
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)

        expected_dependent_ids = set([C.case_id, E1.case_id, E2.case_id])
        self.assertEqual(sync_log.dependent_case_ids_on_phone, expected_dependent_ids)

        all_ids = set([E1.case_id, E2.case_id, O.case_id, C.case_id])
        self.assertEqual(sync_log.case_ids_on_phone, all_ids)


class ExtensionCasesFirstSync(SyncBaseTest):
    def setUp(self):
        super(ExtensionCasesFirstSync, self).setUp()
        self.restore_config = RestoreConfig(project=self.project, user=self.user)
        self.restore_state = self.restore_config.restore_state

    @run_with_all_backends
    def test_is_first_extension_sync(self):
        """Before any syncs, this should return true when the toggle is enabled, otherwise false"""
        with flag_enabled('EXTENSION_CASES_SYNC_ENABLED'):
            self.assertTrue(self.restore_state.is_first_extension_sync)

        self.assertFalse(self.restore_state.is_first_extension_sync)

    @run_with_all_backends
    def test_is_first_extension_sync_after_sync(self):
        """After a sync with the extension code in place, this should be false"""
        self.factory.create_case()
        with flag_enabled('EXTENSION_CASES_SYNC_ENABLED'):
            config = get_restore_config(self.project, self.user, restore_id=self.sync_log._id)
            self.assertTrue(get_properly_wrapped_sync_log(self.sync_log._id).extensions_checked)
            self.assertFalse(config.restore_state.is_first_extension_sync)

        config = get_restore_config(self.project, self.user, restore_id=self.sync_log._id)
        self.assertTrue(get_properly_wrapped_sync_log(self.sync_log._id).extensions_checked)
        self.assertFalse(config.restore_state.is_first_extension_sync)


class ChangingOwnershipTest(SyncBaseTest):

    def setUp(self):
        super(ChangingOwnershipTest, self).setUp()
        self.extra_owner_id = 'extra-owner-id'
        self.user.additional_owner_ids = [self.extra_owner_id]
        self.sync_log = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.user)
        )
        self.assertTrue(self.extra_owner_id in self.sync_log.owner_ids_on_phone)

        # since we got a new sync log, have to update the factory as well
        self.factory.form_extras = {'last_sync_token': self.sync_log._id}

    @run_with_all_backends
    def test_change_owner_list(self):
        # create a case with the extra owner
        case_id = self.factory.create_case(owner_id=self.extra_owner_id).case_id

        # make sure it's there
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(sync_log.phone_is_holding_case(case_id))

        def _get_incremental_synclog_for_user(user, since):
            incremental_restore_config = RestoreConfig(
                self.project,
                user=self.user,
                params=RestoreParams(version=V2, sync_log_id=since),
            )
            return synclog_from_restore_payload(incremental_restore_config.get_payload().as_string())

        # make sure it's there on new sync
        incremental_sync_log = _get_incremental_synclog_for_user(self.user, since=self.sync_log._id)
        self.assertTrue(self.extra_owner_id in incremental_sync_log.owner_ids_on_phone)
        self.assertTrue(incremental_sync_log.phone_is_holding_case(case_id))

        # remove the owner id and confirm that owner and case are removed on next sync
        self.user.additional_owner_ids = []
        incremental_sync_log = _get_incremental_synclog_for_user(self.user, since=incremental_sync_log._id)
        self.assertFalse(self.extra_owner_id in incremental_sync_log.owner_ids_on_phone)
        self.assertFalse(incremental_sync_log.phone_is_holding_case(case_id))


class SyncTokenCachingTest(SyncBaseTest):

    @run_with_all_backends
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

    @run_with_all_backends
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

    @run_with_all_backends
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

    @run_with_all_backends
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

    @run_with_all_backends
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

    @run_with_all_backends
    def testSharedCase(self):
        # create a case by one user
        case_id = "shared_case"
        self._createCaseStubs([case_id], owner_id=SHARED_ID)
        # should sync to the other owner
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

    @run_with_all_backends
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
                      update={'greeting': "Hello!"}
        ).as_xml(), latest_sync.get_id)

        # original user syncs again
        # make sure updates take
        _, match = assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        self.assertTrue("Hello!" in match.to_string())

    @run_with_all_backends
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
        ).as_xml()

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
                index={'mother': ('mother', mother_id)}
            ).as_xml(),
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
        ).as_xml()

        check_user_has_case(self, self.user, expected_parent_case,
                            restore_id=self.sync_log.get_id, purge_restore_cache=True)
        _, orig = assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        self.assertTrue("index" in orig.to_string())

    @run_with_all_backends
    def testMultiUserEdits(self):
        time = datetime.utcnow()

        # create a case from one user
        case_id = "multi_user_edits"
        self._createCaseStubs([case_id], owner_id=SHARED_ID, date_modified=time)

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
            update={'greeting': 'hello'}
        ).as_xml()
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
            date_modified=time,
            case_id=case_id,
            user_id=USER_ID,
            update={
                'greeting': 'hello',
                'greeting_2': 'hello'
            },
            owner_id=SHARED_ID,
            case_name='',
            case_type='mother',
        ).as_xml()

        check_user_has_case(self, self.user, joint_change, restore_id=main_sync_log.get_id)
        check_user_has_case(self, self.other_user, joint_change, restore_id=self.other_sync_log.get_id)

    @run_with_all_backends
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
            close=True
        ).as_xml()
        self._postFakeWithSyncToken(
            close_block,
            other_sync_log.get_id
        )

        # original user syncs again
        # make sure close block appears
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log._id)

        # make sure closed cases don't show up in the next sync log
        next_synclog = synclog_from_restore_payload(
            generate_restore_payload(self.project, self.user, restore_id=self.sync_log._id)
        )
        self.assertFalse(next_synclog.phone_is_holding_case(case_id))

    @run_with_all_backends
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
            update={'greeting': 'hello'}
        ).as_xml()
        self._postFakeWithSyncToken(
            update,
            self.other_sync_log.get_id
        )

        # original user syncs again
        # make sure there are no new changes
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

    @run_with_all_backends
    def testIndexesSync(self):
        # create a parent and child case (with index) from one user
        parent_id = "indexes_sync_parent"
        case_id = "indexes_sync"
        self._createCaseStubs([parent_id], owner_id=USER_ID)
        child = CaseBlock(
            create=True,
            case_id=case_id,
            user_id=USER_ID,
            owner_id=USER_ID,
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
            update={"greeting": "hello"}
        ).as_xml()
        self._postFakeWithSyncToken(child_update, self.sync_log.get_id)
        # second user syncs
        # make sure both cases restore
        assert_user_has_case(self, self.other_user, parent_id, restore_id=self.other_sync_log.get_id,
                             purge_restore_cache=True)
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

    @run_with_all_backends
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
            update={"greeting": "hello"}).as_xml()
        self._postFakeWithSyncToken(parent_update, self.sync_log.get_id)

        main_sync_log = get_properly_wrapped_sync_log(self.sync_log.get_id)

        # these tests added to debug another issue revealed by this test
        self.assertTrue(main_sync_log.phone_is_holding_case(case_id))
        self.assertTrue(main_sync_log.phone_is_holding_case(parent_id))

        # make sure the other user gets the reassigned case
        assert_user_has_case(self, self.other_user, parent_id, restore_id=self.other_sync_log.get_id,
                             purge_restore_cache=True)
        # update the parent case from another user
        self.other_sync_log = SyncLog.last_for_user(OTHER_USER_ID)
        other_parent_update = CaseBlock(
            create=False,
            case_id=parent_id,
            user_id=OTHER_USER_ID,
            update={"greeting2": "hi"},
        ).as_xml()
        self._postFakeWithSyncToken(other_parent_update, self.other_sync_log.get_id)

        # make sure the indexed case syncs again
        latest_sync_log = SyncLog.last_for_user(USER_ID)
        assert_user_has_case(self, self.user, parent_id, restore_id=latest_sync_log.get_id,
                             purge_restore_cache=True)

    @run_with_all_backends
    def testOtherUserReassignsIndexed(self):
        # create a parent and child case (with index) from one user
        parent_id = "other_reassigns_index_parent"
        case_id = "other_reassigns_index_child"
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=case_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship=CHILD_RELATIONSHIP,
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
            update={"greeting": "hello"}).as_xml()
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
            update={"childgreeting": "hi!"},
        ).as_xml()
        self._postFakeWithSyncToken(child_reassignment, other_sync_log.get_id)

        # also change the parent from the second user
        other_parent_update = CaseBlock(
            create=False,
            case_id=parent_id,
            user_id=OTHER_USER_ID,
            owner_id=OTHER_USER_ID,
            update={"other_greeting": "something new"}).as_xml()
        self._postFakeWithSyncToken(other_parent_update, other_sync_log.get_id)

        # original user syncs again
        latest_sync_log = SyncLog.last_for_user(self.user.user_id)

        # at this point both cases are assigned to the other user so the original user
        # should not have them. however, the first sync should send them down (with new ownership)
        # so that they can be purged.
        assert_user_has_case(self, self.user, case_id, restore_id=latest_sync_log.get_id)
        assert_user_has_case(self, self.user, parent_id, restore_id=latest_sync_log.get_id)

        # Ghetto
        payload = generate_restore_payload(self.project, self.user, latest_sync_log.get_id, version=V2)
        self.assertTrue("something new" in payload)
        self.assertTrue("hi!" in payload)
        # also check that the latest sync log knows those cases are no longer relevant to the phone
        log = synclog_from_restore_payload(payload)
        self.assertFalse(log.phone_is_holding_case(case_id))
        self.assertFalse(log.phone_is_holding_case(parent_id))

        # change the parent again from the second user
        other_parent_update = CaseBlock(
            create=False,
            case_id=parent_id,
            user_id=OTHER_USER_ID,
            owner_id=OTHER_USER_ID,
            update={"other_greeting": "something different"}).as_xml()
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

    @run_with_all_backends
    def testComplicatedGatesBug(self):
        # found this bug in the wild, used the real (test) forms to fix it
        # just running through this test used to fail hard, even though there
        # are no asserts
        folder_path = os.path.join("bugs", "dependent_case_conflicts")
        files = ["reg1.xml", "reg2.xml", "cf.xml", "close.xml"]
        for f in files:
            form = self._postWithSyncToken(os.path.join(folder_path, f), self.sync_log.get_id)
            self.assertFalse(hasattr(form, "problem") and form.problem)
            synclog_from_restore_payload(
                generate_restore_payload(self.project, self.user, version="2.0")
            )

    @run_with_all_backends
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
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={'create': True, 'owner_id': uuid.uuid4().hex}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                    identifier=PARENT_TYPE,
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

    @run_with_all_backends
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
                indices=[
                    CaseIndex(
                        CaseStructure(case_id=mom_id, attrs={'create': True}),
                        relationship=CHILD_RELATIONSHIP,
                        related_type='mom',
                        identifier='mom',
                    ),
                    CaseIndex(
                        CaseStructure(case_id=dad_id, attrs={'create': True}),
                        relationship=CHILD_RELATIONSHIP,
                        related_type='dad',
                        identifier='dad',
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
                    indices=[
                        CaseIndex(
                            CaseStructure(case_id=new_mom_id, attrs={'create': True}),
                            relationship=CHILD_RELATIONSHIP,
                            related_type='mom',
                            identifier='mom',
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


class SteadyStateExtensionSyncTest(SyncBaseTest):
    """
    Test that doing multiple clean syncs with extensions does what we think it will
    """
    def setUp(self):
        super(SteadyStateExtensionSyncTest, self).setUp()
        self.other_user = User(user_id=OTHER_USER_ID, username=OTHER_USERNAME,
                               password="changeme", date_joined=datetime(2011, 6, 9),
                               additional_owner_ids=[SHARED_ID])
        self._create_ownership_cleanliness(USER_ID)
        self._create_ownership_cleanliness(OTHER_USER_ID)

    def _create_ownership_cleanliness(self, user_id):
        OwnershipCleanlinessFlag.objects.get_or_create(
            owner_id=USER_ID,
            domain=self.project.name,
            defaults={'is_clean': True}
        )

    def _create_extension(self):
        host = CaseStructure(case_id='host',
                             attrs={'create': True})
        extension = CaseStructure(
            case_id='extension',
            attrs={'create': True, 'owner_id': '-'},
            indices=[CaseIndex(
                host,
                identifier='idx',
                relationship='extension',
                related_type='case_type',
            )],
        )
        # Make a simple extension
        self.factory.create_or_update_case(extension)
        return host, extension

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    @run_with_all_backends
    def test_delegating_extensions(self):
        """Make an extension, delegate it, send it back, see what happens"""
        host, extension = self._create_extension()

        # Make sure we get it
        assert_user_has_case(self, self.user, host.case_id)
        # But ferrel doesn't
        assert_user_doesnt_have_case(self, self.other_user, host.case_id)

        # Reassign the extension to ferrel
        re_assigned_extension = CaseStructure(
            case_id='extension',
            attrs={'owner_id': OTHER_USER_ID}
        )
        self.factory.create_or_update_case(re_assigned_extension)

        # other user should sync the host
        assert_user_has_case(self, self.other_user, host.case_id)

        # original user should sync the extension because it has changed
        sync_log_id = SyncLog.last_for_user(USER_ID)._id
        assert_user_has_case(self, self.user, extension.case_id,
                             restore_id=sync_log_id)
        # but not the host, because that didn't
        assert_user_doesnt_have_case(self, self.user, host.case_id,
                                     restore_id=sync_log_id)

        # syncing again by original user should not pull anything
        sync_again_id = SyncLog.last_for_user(USER_ID)._id
        assert_user_doesnt_have_case(self, self.user, extension.case_id,
                                     restore_id=sync_again_id)
        assert_user_doesnt_have_case(self, self.user, host.case_id,
                                     restore_id=sync_again_id)

        # reassign the extension case
        re_assigned_extension = CaseStructure(
            case_id='extension',
            attrs={'owner_id': '-'}
        )
        self.factory.create_or_update_case(re_assigned_extension)

        # make sure other_user gets it because it changed
        assert_user_has_case(self, self.other_user, extension.case_id,
                             restore_id=SyncLog.last_for_user(OTHER_USER_ID)._id)
        # first user should also get it since it was updated
        assert_user_has_case(self, self.user, extension.case_id, restore_id=SyncLog.last_for_user(USER_ID)._id)

        # other user syncs again, should not get the extension
        assert_user_doesnt_have_case(self, self.other_user, extension.case_id,
                                     restore_id=SyncLog.last_for_user(OTHER_USER_ID)._id)

        # Hooray!

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    @run_with_all_backends
    def test_multiple_syncs(self):
        host, extension = self._create_extension()
        assert_user_has_case(self, self.user, host.case_id)
        assert_user_has_case(self, self.user, extension.case_id)

        sync_log = SyncLog.last_for_user(USER_ID)
        self.assertItemsEqual(sync_log.case_ids_on_phone, ['host', 'extension'])

        generate_restore_payload(self.project, self.user, restore_id=sync_log._id, version=V2)
        second_sync_log = SyncLog.last_for_user(USER_ID)
        self.assertItemsEqual(second_sync_log.case_ids_on_phone, ['host', 'extension'])

        generate_restore_payload(self.project, self.user, restore_id=second_sync_log._id, version=V2)
        third_sync_log = SyncLog.last_for_user(USER_ID)
        self.assertItemsEqual(third_sync_log.case_ids_on_phone, ['host', 'extension'])


class SyncTokenReprocessingTest(SyncBaseTest):
    """
    Tests sync token logic for fixing itself when it gets into a bad state.
    """

    @run_with_all_backends
    def testUpdateNonExisting(self):
        case_id = 'non_existent'
        caseblock = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=USER_ID,
            owner_id=USER_ID,
            case_type=PARENT_TYPE,
        ).as_xml()
        try:
            self._postFakeWithSyncToken(caseblock, self.sync_log.get_id)
            self.fail('posting an update to a non-existant case should fail')
        except AssertionError:
            # this should fail because it's a true error
            pass

    @run_with_all_backends
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
            update={'something': "changed"},
        ).as_xml()

        # this should work because it should magically fix itself
        self._postFakeWithSyncToken(update, self.sync_log.get_id)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertFalse(getattr(sync_log, 'has_assert_errors', False))

    @run_with_all_backends
    def testCodependencies(self):

        case_id1 = 'bad1'
        case_id2 = 'bad2'
        initial_caseblocks = [CaseBlock(
            create=True,
            case_id=case_id,
            user_id='not_me',
            owner_id='not_me',
            case_type=PARENT_TYPE,
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

    @run_with_all_backends
    def test_submission_with_bad_log_default(self):
        with self.assertRaises(ResourceNotFound):
            post_case_blocks(
                [CaseBlock(create=True, case_id='bad-log-default').as_xml()],
                form_extras={"last_sync_token": 'not-a-valid-synclog-id'},
                domain='some-domain-without-toggle',
            )

    @run_with_all_backends
    def test_submission_with_bad_log_toggle_enabled(self):
        domain = 'submission-domain-with-toggle'

        def _test():
            post_case_blocks(
                [CaseBlock(create=True, case_id='bad-log-toggle-enabled').as_xml()],
                form_extras={"last_sync_token": 'not-a-valid-synclog-id'},
                domain=domain,
            )

        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, False, namespace='domain')
        with self.assertRaises(ResourceNotFound):
            _test()

        LOOSE_SYNC_TOKEN_VALIDATION.set(domain, True, namespace='domain')
        # this is just asserting that an exception is not raised after the toggle is set
        _test()

    @run_with_all_backends
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

    @run_with_all_backends
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
