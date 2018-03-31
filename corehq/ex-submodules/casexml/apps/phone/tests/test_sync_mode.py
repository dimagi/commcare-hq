from __future__ import absolute_import
from __future__ import unicode_literals
import os
import uuid
from datetime import datetime
from xml.etree import cElementTree as ElementTree
from django.test.utils import override_settings
from django.test import TestCase

from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.exceptions import RestoreException
from casexml.apps.phone.restore_caching import RestorePayloadPathCache
from casexml.apps.case.mock import CaseBlock, CaseStructure, CaseIndex
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.phone.utils import get_restore_config, MockDevice
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from corehq.apps.domain.models import Domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.groups.models import Group
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.blobs import get_blob_db
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    use_sql_backend,
)
from corehq.util.test_utils import flag_enabled
from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
from casexml.apps.phone.models import (
    AbstractSyncLog,
    get_properly_wrapped_sync_log,
    LOG_FORMAT_LIVEQUERY,
    LOG_FORMAT_SIMPLIFIED,
    SimplifiedSyncLog,
)
from casexml.apps.phone.restore import (
    CachedResponse,
    CLEAN_OWNERS,
    LIVEQUERY,
    RestoreConfig,
    RestoreParams,
    RestoreCacheSettings,
)
from casexml.apps.case.xml import V2, V1
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from six.moves import range

USERNAME = "syncguy"
OTHER_USERNAME = "ferrel"
PARENT_TYPE = "mother"
CHILD_RELATIONSHIP = "child"


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class BaseSyncTest(TestCase):
    """
    Shared functionality among tests
    """
    restore_options = {'case_sync': CLEAN_OWNERS}

    @classmethod
    def setUpClass(cls):
        super(BaseSyncTest, cls).setUpClass()
        delete_all_users()

        cls.project = Domain(name=TEST_DOMAIN_NAME)
        cls.project.save()
        cls.user = create_restore_user(
            cls.project.name,
            USERNAME,
        )
        cls.user_id = cls.user.user_id
        # this creates the initial blank sync token in the database

    def setUp(self):
        super(BaseSyncTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases()
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_sync_logs()
        self.device = self.get_device()
        self.device.sync(overwrite_cache=True, version=V1)

    def tearDown(self):
        restore_config = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            **self.restore_options
        )
        restore_config.restore_payload_path_cache.invalidate()
        super(BaseSyncTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        delete_all_domains()
        super(BaseSyncTest, cls).tearDownClass()

    def get_device(self, **kw):
        kw.setdefault("project", self.project)
        kw.setdefault("user", self.user)
        kw.setdefault("restore_options", self.restore_options)
        kw.setdefault("default_case_type", PARENT_TYPE)
        return MockDevice(**kw)

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
            # livequery sync does not use or populate sync_log.index_tree
            if self.restore_options['case_sync'] == LIVEQUERY:
                self.assertEqual(sync_log.log_format, LOG_FORMAT_LIVEQUERY)
            else:
                self.assertEqual(sync_log.log_format, LOG_FORMAT_SIMPLIFIED)
                self.assertEqual(set(dependent_case_id_map.keys()), sync_log.dependent_case_ids_on_phone)
                for case_id, indices in case_id_map.items():
                    if indices:
                        index_ids = [i.referenced_id for i in case_id_map[case_id]]
                        self._checkLists(index_ids, list(sync_log.index_tree.indices[case_id].values()),
                                         'case {} has unexpected indices'.format(case_id))
                for case_id, indices in dependent_case_id_map.items():
                    if indices:
                        index_ids = [i.referenced_id for i in case_id_map[case_id]]
                        self._checkLists(index_ids, list(sync_log.index_tree.indices[case_id].values()))

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


class DeprecatedBaseSyncTest(BaseSyncTest):
    """DEPRECATED use BaseSyncTest when making new subclasses

    This base class has `self.factory` and `self.sync_log`, which
    are superseded by `self.device` (`MockDevice`).
    """

    def setUp(self):
        super(DeprecatedBaseSyncTest, self).setUp()
        self.sync_log = self.device.last_sync.log
        self.factory = self.device.case_factory
        self.factory.form_extras = {
            'last_sync_token': self.sync_log._id,
        }


class SyncTokenUpdateTest(BaseSyncTest):
    """
    Tests sync token updates on submission related to the list of cases
    on the phone and the footprint.
    """

    def testInitialEmpty(self):
        """
        Tests that a newly created sync token has no cases attached to it.
        """
        self._testUpdate(self.device.last_sync.log.get_id, {}, {})

    def testOwnUpdatesDontSync(self):
        case_id = "own_updates_dont_sync"
        self.device.change_cases(case_id=case_id, create=True)
        self.assertEqual(self.device.sync().cases, {})

        self.device.change_cases(
            CaseStructure(case_id=case_id, attrs={'update': {"greeting": "hello"}}),
        )
        self.assertEqual(self.device.sync().cases, {})

        self.device.change_cases(
            CaseStructure(case_id=case_id, attrs={'owner_id': 'do-not-own-this'}),
        )
        self.assertEqual(self.device.sync().cases, {})

    def test_change_index_type(self):
        """
        Test that changing an index type updates the sync log
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # update the child's index (parent type)
        updated_type = "updated_type"
        self.device.post_changes(CaseBlock(
            create=False, case_id=child_id, user_id=self.user_id,
            index={index_id: (updated_type, parent_id)},
        ))
        parent_ref.referenced_type = updated_type
        self._testUpdate(self.device.last_sync.log._id,
            {parent_id: [], child_id: [parent_ref]})

    def test_change_index_id(self):
        """
        Test that changing an index ID updates the sync log
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()

        # update the child's index (parent id)
        updated_id = 'changed_index_id'
        self.device.post_changes(CaseStructure(
            case_id=child_id,
            indices=[CaseIndex(
                CaseStructure(case_id=updated_id, attrs={'create': True}),
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
                identifier=index_id,
            )],
        ))
        parent_ref.referenced_id = updated_id
        self._testUpdate(self.device.last_sync.log.get_id,
            {parent_id: [], updated_id: [], child_id: [parent_ref]})

    def test_add_multiple_indices(self):
        """
        Test that adding multiple indices works as expected
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # add new index
        new_case_id = 'new_case_id'
        new_index_identifier = 'new_index_id'

        self.device.post_changes(CaseStructure(
            case_id=child_id,
            indices=[CaseIndex(
                CaseStructure(case_id=new_case_id, attrs={'create': True}),
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
                identifier=new_index_identifier,
            )],
        ))
        new_index_ref = CommCareCaseIndex(
            identifier=new_index_identifier,
            referenced_type=PARENT_TYPE,
            referenced_id=new_case_id,
        )

        self._testUpdate(self.device.last_sync.log.get_id,
            {parent_id: [], new_case_id: [], child_id: [parent_ref, new_index_ref]})

    def test_delete_only_index(self):
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # delete the first index
        self.device.post_changes(CaseBlock(
            create=False,
            case_id=child_id,
            user_id=self.user_id,
            index={index_id: (PARENT_TYPE, "")},
        ))
        self._testUpdate(self.device.last_sync.log.get_id, {parent_id: [], child_id: []})

    def test_delete_one_of_multiple_indices(self):
        # make IDs both human readable and globally unique to this test
        uid = uuid.uuid4().hex
        child_id = 'child_id-{}'.format(uid)
        parent_id_1 = 'parent_id-{}'.format(uid)
        index_id_1 = 'parent_index_id-{}'.format(uid)
        parent_id_2 = 'parent_id_2-{}'.format(uid)
        index_id_2 = 'parent_index_id_2-{}'.format(uid)

        self.device.post_changes(CaseStructure(
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
        self._testUpdate(self.device.last_sync.log.get_id, {parent_id_1: [], parent_id_2: [],
                                                child_id: [parent_ref_1, parent_ref_2]})

        # delete the first index
        self.device.post_changes(CaseBlock(
            create=False,
            case_id=child_id,
            user_id=self.user_id,
            index={index_id_1: (PARENT_TYPE, "")},
        ))
        self._testUpdate(self.device.last_sync.log.get_id,
            {parent_id_1: [], parent_id_2: [], child_id: [parent_ref_2]})

    def _initialize_parent_child(self):
        child_id = "child_id"
        parent_id = "parent_id"
        index_id = 'parent_index_id'
        self.device.post_changes(CaseStructure(
            case_id=child_id,
            attrs={'create': True},
            indices=[CaseIndex(
                CaseStructure(case_id=parent_id, attrs={'create': True}),
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
                identifier=index_id,
            )],
        ))
        parent_ref = CommCareCaseIndex(
            identifier=index_id,
            referenced_type=PARENT_TYPE,
            referenced_id=parent_id,
        )
        self._testUpdate(self.device.last_sync.log._id, {parent_id: [], child_id: [parent_ref]})
        return (child_id, parent_id, index_id, parent_ref)

    def testClosedParentIndex(self):
        """
        Tests that things work properly when you have a reference to the parent
        case in a child, even if it's closed.
        """
        parent_id = "mommy"
        child_id = "baby"
        index_id = 'my_mom_is'
        self.device.post_changes([
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

        self._testUpdate(self.device.last_sync.log.get_id,
            {parent_id: [], child_id: [index_ref]})

        # close the mother case
        close = CaseBlock(create=False, case_id=parent_id, user_id=self.user_id, close=True)
        self.device.post_changes(close)
        self._testUpdate(self.device.last_sync.log.get_id, {child_id: [index_ref]},
                         {parent_id: []})

        # try a clean restore again
        self.device.last_sync = None
        self.assertEqual(set(self.device.sync().cases), {parent_id, child_id})

    def testAssignToNewOwner(self):
        # create parent and child
        parent_id = "mommy"
        child_id = "baby"
        index_id = 'my_mom_is'
        self.device.post_changes([
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
        self._testUpdate(self.device.last_sync.log.get_id,
            {parent_id: [], child_id: [index_ref]})

        # assign the child to a new owner
        new_owner = "not_mine"
        self.device.post_changes(
            CaseBlock(create=False, case_id=child_id, user_id=self.user_id, owner_id=new_owner),
        )

        # child should be moved, parent should still be there
        self._testUpdate(self.device.last_sync.log.get_id, {parent_id: []}, {})

    def testArchiveUpdates(self):
        """
        Tests that archiving a form (and changing a case) causes the
        case to be included in the next sync.
        """
        case_id = "archive_syncs"
        self.device.change_cases(case_id=case_id, create=True)
        self.assertEqual(self.device.sync().cases, {})

        self.device.change_cases(CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.user_id,
            update={"greeting": "hello"}
        ))
        sync = self.device.sync()
        self.assertEqual(sync.cases, {})

        sync.form.archive()
        RestorePayloadPathCache(
            domain=self.project.name,
            user_id=self.user_id,
            sync_log_id=sync.restore_id,
            device_id=None,
        ).invalidate()
        self.assertEqual(set(self.device.sync().cases), {case_id})

    def testUserLoggedIntoMultipleDevices(self):
        # test that a child case created by the same user from a different device
        # gets included in the sync
        parent_id = "parent"
        child_id = "child"
        self.device.post_changes(case_id=parent_id, create=True)

        # create child case using a different sync log ID
        device2 = self.get_device(sync=True)
        device2.post_changes(
            create=True,
            case_id=child_id,
            index={'mother': ('mother', parent_id)}
        )

        # ensure child case is included in sync using original sync log ID
        self.assertIn(child_id, self.device.sync().cases)

    def test_tiered_parent_closing(self):
        all_ids = [uuid.uuid4().hex for i in range(3)]
        [grandparent_id, parent_id, child_id] = all_ids
        self.device.post_changes([
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
        self.device.post_changes(case_id=grandparent_id, close=True)
        sync_log = self.device.last_sync.get_log()
        for id in all_ids:
            self.assertTrue(sync_log.phone_is_holding_case(id))

        self.device.post_changes(case_id=parent_id, close=True)
        sync_log = self.device.last_sync.get_log()
        for id in all_ids:
            self.assertTrue(sync_log.phone_is_holding_case(id))

        self.device.post_changes(case_id=child_id, close=True)
        sync_log = self.device.last_sync.get_log()
        for id in all_ids:
            # once the child is closed, all three are no longer relevant
            self.assertFalse(sync_log.phone_is_holding_case(id))

    def test_create_immediately_irrelevant_parent_case(self):
        """
        Make a case that is only relevant through a dependency at the same
        time as the dependency is made. Make sure it is relevant.
        """
        # create a parent and child case (with index) from one user
        parent_id, child_id = [uuid.uuid4().hex for i in range(2)]
        self.device.post_changes([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={
                        'create': True,
                        'owner_id': uuid.uuid4().hex,
                    }),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                    identifier=PARENT_TYPE,
                )],
            )
        ])
        index_ref = CommCareCaseIndex(identifier=PARENT_TYPE,
                                      referenced_type=PARENT_TYPE,
                                      referenced_id=parent_id)
        self._testUpdate(self.device.last_sync.log._id,
            {child_id: [index_ref]}, {parent_id: []})

    def test_closed_case_not_in_next_sync(self):
        # create a case
        case_id = uuid.uuid4().hex
        self.device.change_cases(case_id=case_id, create=True)
        # sync
        sync = self.device.sync()
        self.assertTrue(sync.log.phone_is_holding_case(case_id))
        # close the case on the second sync
        self.device.change_cases(case_id=case_id, close=True)
        self.device.sync()
        # sync again
        sync = self.device.sync()
        self.assertFalse(sync.log.phone_is_holding_case(case_id))

    def test_sync_by_user_id(self):
        # create a case with an empty owner but valid user id
        case_id = 'empty-owner'
        self.device.change_cases(case_id=case_id, owner_id='', create=True)
        sync = self.device.sync(restore_id='')
        self.assertIn(case_id, sync.cases)
        self.assertTrue(sync.log.phone_is_holding_case(case_id))

    def test_create_irrelevant_owner_and_update_to_irrelevant_owner_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        self.device.post_changes(
            create=True,
            owner_id='irrelevant_1',
            update={'owner_id': 'irrelevant_2'},
            strict=False,
        )

    def test_create_irrelevant_owner_and_update_to_relevant_owner_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        case_id = 'edge'
        self.device.post_changes(
            create=True,
            case_id=case_id,
            owner_id='irrelevant_1',
            update={'owner_id': self.user_id},
            strict=False,
        )
        sync_log = self.device.last_sync.get_log()
        self.assertTrue(sync_log.phone_is_holding_case(case_id))

    def test_create_relevant_owner_and_update_to_empty_owner_in_same_form(self):
        case_id = 'edge'
        self.device.post_changes(
            create=True,
            case_id=case_id,
            owner_id=self.user_id,
            update={'owner_id': ''},
            strict=False,
        )
        sync_log = self.device.last_sync.get_log()
        self.assertFalse(sync_log.phone_is_holding_case(case_id))

    def test_create_irrelevant_owner_and_update_to_empty_owner_in_same_form(self):
        case_id = 'edge'
        self.device.post_changes(
            create=True,
            case_id=case_id,
            owner_id='irrelevant_1',
            update={'owner_id': ''},
            strict=False,
        )
        sync_log = self.device.last_sync.get_log()
        self.assertFalse(sync_log.phone_is_holding_case(case_id))

    def test_create_relevant_owner_then_submit_again_with_no_owner(self):
        case_id = 'relevant_to_no_owner'
        self.device.post_changes(create=True, case_id=case_id)
        sync_log = self.device.last_sync.get_log()
        self.assertTrue(sync_log.phone_is_holding_case(case_id))
        self.device.post_changes(CaseStructure(
            case_id=case_id,
            attrs={'owner_id': None}
        ))
        sync_log = self.device.last_sync.get_log()
        self.assertTrue(sync_log.phone_is_holding_case(case_id))

    def test_create_irrelevant_owner_then_submit_again_with_no_owner(self):
        case_id = 'irrelevant_to_no_owner'
        self.device.post_changes(create=True, case_id=case_id, owner_id='irrelevant_1')
        sync_log = self.device.last_sync.get_log()
        self.assertFalse(sync_log.phone_is_holding_case(case_id))
        self.device.post_changes(CaseStructure(
            case_id=case_id,
            attrs={'owner_id': None}
        ))
        sync_log = self.device.last_sync.get_log()
        self.assertFalse(sync_log.phone_is_holding_case(case_id))

    def test_create_irrelevant_child_case_and_close_parent_in_same_form(self):
        # create the parent
        parent_id = uuid.uuid4().hex
        self.device.post_changes(create=True, case_id=parent_id)
        # create an irrelevent child and close the parent
        child_id = uuid.uuid4().hex
        self.device.post_changes([
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
        self._testUpdate(self.device.last_sync.log._id, {}, {})

    def test_create_closed_child_case_and_close_parent_in_same_form(self):
        # create the parent
        parent_id = uuid.uuid4().hex
        self.device.post_changes(create=True, case_id=parent_id)
        # create an irrelevent child and close the parent
        child_id = uuid.uuid4().hex
        self.device.post_changes([
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
        self._testUpdate(self.device.last_sync.log._id, {}, {})

    def test_create_irrelevant_owner_and_close_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        self.device.post_changes(create=True, owner_id='irrelevant_1', close=True)

    def test_reassign_and_close_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        case_id = "edge"
        self.device.post_changes(create=True, case_id=case_id)
        self.device.post_changes(
            CaseStructure(
                case_id=case_id,
                attrs={'owner_id': 'irrelevant', 'close': True},
            )
        )

    def test_index_after_close(self):
        parent_id = uuid.uuid4().hex
        self.device.post_changes(create=True, case_id=parent_id)
        case_id = uuid.uuid4().hex
        case_xml = self.device.case_factory.get_case_block(
            case_id, create=True, close=True)
        # hackily insert an <index> block after the close
        index_wrapper = ElementTree.Element('index')
        index_elem = ElementTree.Element('parent')
        index_elem.set('case_type', 'test')
        index_elem.set('relationship', 'child')
        index_elem.text = parent_id
        index_wrapper.append(index_elem)
        case_xml.append(index_wrapper)
        self.device.case_blocks.append(case_xml)
        self.device.post_changes()
        sync_log = self.device.last_sync.get_log()
        # before this test was written, the case stayed on the sync log even though it was closed
        self.assertFalse(sync_log.phone_is_holding_case(case_id))

    def test_index_chain_with_closed_parents(self):
        grandparent = CaseStructure(
            case_id='grandparent',
            attrs={'close': True, 'create': True}
        )
        parent = CaseStructure(
            case_id='parent',
            attrs={'close': True, 'create': True},
            indices=[CaseIndex(
                grandparent,
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
            )]
        )
        child = CaseStructure(
            case_id='child',
            indices=[CaseIndex(
                parent,
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
            )],
            attrs={'create': True}
        )
        parent_ref = CommCareCaseIndex(
            identifier=PARENT_TYPE,
            referenced_type=PARENT_TYPE,
            referenced_id=parent.case_id)
        grandparent_ref = CommCareCaseIndex(
            identifier=PARENT_TYPE,
            referenced_type=PARENT_TYPE,
            referenced_id=grandparent.case_id)

        self.device.post_changes(child)

        self._testUpdate(
            self.device.last_sync.log._id,
            {child.case_id: [parent_ref],
             parent.case_id: [grandparent_ref],
             grandparent.case_id: []},
            {parent.case_id: [grandparent.case_id],
             grandparent.case_id: []}
        )

    def test_reassign_case_and_sync(self):
        case_id = uuid.uuid4().hex
        self.device.post_changes(create=True, case_id=case_id)
        # reassign from an empty sync token, simulating a web-reassignment on HQ
        web = self.get_device()
        web.post_changes(
            CaseStructure(
                case_id=case_id,
                attrs={'owner_id': 'irrelevant'},
            ),
        )
        self.assertIn(case_id, self.device.sync().cases)
        self.assertNotIn(case_id, self.device.sync().cases)

    def test_cousins(self):
        """http://manage.dimagi.com/default.asp?189528
        """
        other_owner_id = uuid.uuid4().hex
        grandparent = CaseStructure(
            case_id="Steffon",
            attrs={'owner_id': other_owner_id, 'create': True}
        )
        parent_1 = CaseStructure(
            case_id="Stannis",
            attrs={'owner_id': other_owner_id, 'create': True},
            indices=[CaseIndex(grandparent)]
        )
        parent_2 = CaseStructure(
            case_id="Robert",
            attrs={'owner_id': other_owner_id, 'create': True},
            indices=[CaseIndex(grandparent)]
        )
        child_1 = CaseStructure(
            case_id="Shireen",
            indices=[CaseIndex(parent_1)],
            attrs={'create': True}
        )
        child_2 = CaseStructure(
            case_id="Joffrey",
            indices=[CaseIndex(parent_2)],
            attrs={'create': True}
        )
        self.device.post_changes([grandparent, parent_1, parent_2, child_1, child_2])
        self.assertEqual(set(self.device.sync(restore_id='').cases), {
            grandparent.case_id,
            parent_1.case_id,
            parent_2.case_id,
            child_1.case_id,
            child_2.case_id
        })


@use_sql_backend
class SyncTokenUpdateTestSQL(SyncTokenUpdateTest):
    pass


class LiveQuerySyncTokenUpdateTest(SyncTokenUpdateTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySyncTokenUpdateTestSQL(LiveQuerySyncTokenUpdateTest):
    pass


class SyncDeletedCasesTest(BaseSyncTest):

    def test_deleted_case_doesnt_sync(self):
        case_id = uuid.uuid4().hex
        self.device.post_changes(case_id=case_id, create=True)
        CaseAccessors(self.project.name).get_case(case_id).soft_delete()
        self.assertNotIn(case_id, self.device.sync().cases)

    def test_deleted_parent_doesnt_sync(self):
        parent_id = uuid.uuid4().hex
        child_id = uuid.uuid4().hex
        # post with new device so cases are not on self.device
        self.get_device().post_changes(
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                )],
            )
        )
        CaseAccessors().get_case(parent_id).soft_delete()
        self.assertEqual(set(self.device.sync().cases), {child_id})
        # todo: in the future we may also want to purge the child


@use_sql_backend
class SyncDeletedCasesTestSQL(SyncDeletedCasesTest):
    pass


class LiveQuerySyncDeletedCasesTest(SyncDeletedCasesTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySyncDeletedCasesTestSQL(LiveQuerySyncDeletedCasesTest):
    pass


class ExtensionCasesSyncTokenUpdates(BaseSyncTest):
    """Makes sure the extension case trees are propertly updated
    """

    def test_create_extension(self):
        """creating an extension should add it to the extension_index_tree
        """
        case_type = 'case'
        index_identifier = 'idx'
        host = CaseStructure(case_id='host', attrs={'create': True})
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

        self.device.post_changes(extension)
        sync_log = self.device.last_sync.get_log()
        self.assertDictEqual(sync_log.index_tree.indices, {})
        self.assertDictEqual(sync_log.extension_index_tree.indices,
                             {extension.case_id: {index_identifier: host.case_id}})
        self.assertEqual(sync_log.dependent_case_ids_on_phone, set([extension.case_id]))
        self.assertEqual(sync_log.case_ids_on_phone, set([extension.case_id, host.case_id]))

    def test_create_multiple_indices(self):
        """creating multiple indices should add to the right tree
        """
        case_type = 'case'
        host = CaseStructure(case_id='host', attrs={'create': True})
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
        self.device.post_changes(extension)
        sync_log = self.device.last_sync.get_log()
        self.assertDictEqual(sync_log.index_tree.indices,
                             {extension.case_id: {'child': host.case_id}})
        self.assertDictEqual(sync_log.extension_index_tree.indices,
                             {extension.case_id: {'host': host.case_id}})

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
        self.device.post_changes(extension_extension)
        sync_log = self.device.last_sync.get_log()
        expected_extension_tree = {extension.case_id: {'host': host.case_id},
                                   extension_extension.case_id: {'host_2': extension.case_id}}
        self.assertDictEqual(sync_log.index_tree.indices, {})
        self.assertDictEqual(sync_log.extension_index_tree.indices, expected_extension_tree)

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
        delegated_extension = CaseStructure(case_id=extension.case_id, attrs={'owner_id': 'me'})
        self.device.post_changes(extension)
        self.device.post_changes(delegated_extension)

        expected_extension_tree = {extension.case_id: {'host': host.case_id}}
        sync_log = self.device.last_sync.get_log()
        self.assertDictEqual(sync_log.extension_index_tree.indices, expected_extension_tree)
        self.assertEqual(sync_log.dependent_case_ids_on_phone, set([extension.case_id]))
        self.assertEqual(sync_log.case_ids_on_phone, set([extension.case_id, host.case_id]))

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
        self.device.post_changes(extension)

        expected_extension_tree = {extension.case_id: {'host': host.case_id}}
        sync_log = self.device.last_sync.get_log()
        self.assertDictEqual(sync_log.extension_index_tree.indices, expected_extension_tree)
        self.assertEqual(sync_log.case_ids_on_phone, set([host.case_id, extension.case_id]))

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
        self.device.post_changes(extension)
        sync_log = self.device.last_sync.get_log()
        self.assertDictEqual(sync_log.extension_index_tree.indices,
                             {extension.case_id: {index_identifier: host.case_id}})

        closed_host = CaseStructure(case_id=host.case_id, attrs={'close': True})
        self.device.post_changes(closed_host)
        sync_log = self.device.last_sync.get_log()
        self.assertDictEqual(sync_log.extension_index_tree.indices, {})
        self.assertEqual(sync_log.dependent_case_ids_on_phone, set([]))
        self.assertEqual(sync_log.case_ids_on_phone, set([]))

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
        self.device.post_changes([O, E2])
        sync_log = self.device.last_sync.get_log()

        expected_dependent_ids = set([C.case_id, E1.case_id, E2.case_id])
        self.assertEqual(sync_log.dependent_case_ids_on_phone, expected_dependent_ids)

        all_ids = set([E1.case_id, E2.case_id, O.case_id, C.case_id])
        self.assertEqual(sync_log.case_ids_on_phone, all_ids)


@use_sql_backend
class ExtensionCasesSyncTokenUpdatesSQL(ExtensionCasesSyncTokenUpdates):
    pass


class LiveQueryExtensionCasesSyncTokenUpdates(ExtensionCasesSyncTokenUpdates):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryExtensionCasesSyncTokenUpdatesSQL(LiveQueryExtensionCasesSyncTokenUpdates):
    pass


class ExtensionCasesFirstSync(BaseSyncTest):

    def setUp(self):
        super(ExtensionCasesFirstSync, self).setUp()
        self.restore_state = self.device.last_sync.config.restore_state

    def test_is_first_extension_sync(self):
        """Before any syncs, this should return true when the toggle is enabled, otherwise false"""
        with flag_enabled('EXTENSION_CASES_SYNC_ENABLED'):
            self.assertTrue(self.restore_state.is_first_extension_sync)

        self.assertFalse(self.restore_state.is_first_extension_sync)

    def test_is_first_extension_sync_after_sync(self):
        """After a sync with the extension code in place, this should be false"""
        self.device.post_changes(create=True, case_id='first')
        sync0 = self.device.last_sync
        with flag_enabled('EXTENSION_CASES_SYNC_ENABLED'):
            config = get_restore_config(self.project, self.user,
                restore_id=sync0.log._id, **self.restore_options)
            self.assertTrue(sync0.get_log().extensions_checked)
            self.assertFalse(config.restore_state.is_first_extension_sync)

        config = get_restore_config(self.project, self.user,
            restore_id=sync0.log._id, **self.restore_options)
        self.assertTrue(sync0.get_log().extensions_checked)
        self.assertFalse(config.restore_state.is_first_extension_sync)


@use_sql_backend
class ExtensionCasesFirstSyncSQL(ExtensionCasesFirstSync):
    pass


class LiveQueryExtensionCasesFirstSync(ExtensionCasesFirstSync):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryExtensionCasesFirstSyncSQL(LiveQueryExtensionCasesFirstSync):
    pass


class ChangingOwnershipTest(BaseSyncTest):

    def test_remove_user_from_group(self):
        group = Group(
            domain=self.project.name,
            name='remove_user',
            case_sharing=True,
            users=[self.user.user_id]
        )
        group.save()
        sync0 = self.device.sync()
        self.assertIn(group._id, sync0.log.owner_ids_on_phone)

        # create a case owned by the group
        case_id = "chameleon"
        self.device.post_changes(
            create=True,
            case_id=case_id,
            owner_id=group._id,
        )
        # make sure it's there
        self.assertTrue(sync0.get_log().phone_is_holding_case(case_id))

        # make sure it's there on new sync
        sync1 = self.device.sync()
        self.assertIn(group._id, sync1.log.owner_ids_on_phone)
        self.assertTrue(sync1.log.phone_is_holding_case(case_id))

        # remove the owner id and confirm that owner and case are removed on next sync
        group.remove_user(self.user.user_id)
        group.save()
        sync2 = self.device.sync()
        self.assertNotIn(group._id, sync2.log.owner_ids_on_phone)
        self.assertFalse(sync2.log.phone_is_holding_case(case_id))

    def test_add_user_to_group(self):
        group = Group(
            domain=self.project.name,
            name='add_user',
            case_sharing=True,
            users=[]
        )
        group.save()
        # create a case owned by the group
        case_id = uuid.uuid4().hex
        self.device.change_cases(case_id=case_id, owner_id=group._id, create=True)
        # shouldn't be there
        sync1 = self.device.sync()
        self.assertFalse(sync1.log.phone_is_holding_case(case_id))

        group.add_user(self.user.user_id)
        # make sure it's there on new sync
        sync2 = self.device.sync()
        self.assertTrue(group._id in sync2.log.owner_ids_on_phone)
        self.assertTrue(sync2.log.phone_is_holding_case(case_id))


@use_sql_backend
class ChangingOwnershipTestSQL(ChangingOwnershipTest):
    pass


class LiveQueryChangingOwnershipTest(ChangingOwnershipTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryChangingOwnershipTestSQL(LiveQueryChangingOwnershipTest):
    pass


class SyncTokenCachingTest(BaseSyncTest):

    def testCaching(self):
        sync0 = self.device.last_sync
        self.assertFalse(sync0.has_cached_payload(V2))
        # first request should populate the cache
        sync1 = self.device.sync(version=V2, restore_id=sync0.log._id)
        self.assertTrue(sync0.has_cached_payload(V2))

        # a second request with the same config should be exactly the same
        sync2 = self.device.sync(version=V2, restore_id=sync0.log._id)
        self.assertEqual(sync1.payload, sync2.payload)

    def test_initial_cache(self):
        restore_config = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            cache_settings=RestoreCacheSettings(force_cache=True),
            **self.restore_options
        )
        original_payload = restore_config.get_payload()
        self.assertNotIsInstance(original_payload, CachedResponse)

        restore_config = RestoreConfig(
            project=self.project, restore_user=self.user, **self.restore_options)
        cached_payload = restore_config.get_payload()
        self.assertIsInstance(cached_payload, CachedResponse)

    def testCacheInvalidation(self):
        sync0 = self.device.last_sync
        sync1 = self.device.sync(version=V2)
        self.assertTrue(sync0.has_cached_payload(V2))

        # posting a case associated with this sync token should invalidate the cache
        case_id = "cache_invalidation"
        self.device.last_sync = sync0
        self.device.post_changes(case_id=case_id, create=True)
        self.assertFalse(sync0.has_cached_payload(V2))

        # resyncing should recreate the cache
        sync2 = self.device.sync(version=V2)
        self.assertTrue(sync0.has_cached_payload(V2))
        self.assertNotEqual(sync1.payload, sync2.payload)
        self.assertNotIn(case_id, sync1.cases)
        # since it was our own update, it shouldn't be in the new payload either
        self.assertNotIn(case_id, sync2.cases)
        # we can be explicit about why this is the case
        self.assertTrue(sync2.log.phone_is_holding_case(case_id))

    def testCacheNonInvalidation(self):
        sync0 = self.device.last_sync
        sync1 = self.device.sync(version=V2)
        self.assertTrue(sync0.has_cached_payload(V2))

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
        self.device.last_sync = sync0
        sync2 = self.device.sync(version=V2)
        self.assertEqual(sync1.payload, sync2.payload)
        self.assertNotIn(case_id, sync2.cases)

    def testCacheInvalidationAfterFileDelete(self):
        # first request should populate the cache
        config = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            cache_settings=RestoreCacheSettings(force_cache=True),
            **self.restore_options
        )
        original_payload = config.get_payload()
        self.assertNotIsInstance(original_payload, CachedResponse)

        original_name = config.restore_payload_path_cache.get_value()
        self.assertTrue(original_name)
        get_blob_db().delete(original_name)

        # resyncing should recreate the cache
        next_config = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            cache_settings=RestoreCacheSettings(force_cache=True),
            **self.restore_options
        )
        next_file = next_config.get_payload()
        next_name = next_config.restore_payload_path_cache.get_value()
        self.assertNotIsInstance(next_file, CachedResponse)
        self.assertTrue(next_name)
        self.assertNotEqual(original_name, next_name)


@use_sql_backend
class SyncTokenCachingTestSQL(SyncTokenCachingTest):
    pass


class LiveQuerySyncTokenCachingTest(SyncTokenCachingTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySyncTokenCachingTestSQL(LiveQuerySyncTokenCachingTest):
    pass


class MultiUserSyncTest(BaseSyncTest):
    """
    Tests the interaction of two users in sync mode doing various things
    """

    @classmethod
    def setUpClass(cls):
        super(MultiUserSyncTest, cls).setUpClass()
        # the other user is an "owner" of the original users cases as well,
        # for convenience
        cls.other_user = create_restore_user(
            cls.project.name,
            username=OTHER_USERNAME,
        )
        cls.shared_group = Group(
            domain=cls.project.name,
            name='shared_group',
            case_sharing=True,
            users=[cls.other_user.user_id, cls.user.user_id]
        )
        cls.shared_group.save()

    def setUp(self):
        super(MultiUserSyncTest, self).setUp()
        self.guy = self.get_device(
            default_owner_id=self.shared_group._id,
            sync=True,
        )
        self.ferrel = self.get_device(
            user=self.other_user,
            default_owner_id=self.shared_group._id,
            sync=True,
        )
        glog = self.guy.last_sync.log
        self.assertIn(self.shared_group._id, glog.owner_ids_on_phone)
        self.assertIn(self.guy.user_id, glog.owner_ids_on_phone)
        flog = self.ferrel.last_sync.log
        self.assertIn(self.shared_group._id, flog.owner_ids_on_phone)
        self.assertIn(self.ferrel.user_id, flog.owner_ids_on_phone)

    def testSharedCase(self):
        # create a case by one user
        case_id = "shared_case"
        self.guy.post_changes(case_id=case_id, create=True)
        # should sync to the other owner
        self.assertIn(case_id, self.ferrel.sync().cases)

    def testOtherUserEdits(self):
        # create a case by one user
        case_id = "other_user_edits"
        self.guy.post_changes(case_id=case_id, create=True)

        # sync to the other's phone to be able to edit
        self.assertIn(case_id, self.ferrel.sync().cases)

        # update from another
        self.ferrel.post_changes(case_id=case_id, update={'greeting': "Hello!"})

        # original user syncs again
        gsync = self.guy.sync()
        # make sure updates take
        self.assertEqual(gsync.cases[case_id].update, {"greeting": "Hello!"})

    def testOtherUserAddsIndex(self):
        time = datetime.utcnow()
        case_id = "other_user_adds_index"
        mother_id = "other_user_adds_index_mother"

        # create a case from one user
        self.guy.post_changes(case_id=case_id, create=True)

        # sync to the other's phone to be able to edit
        self.assertIn(case_id, self.ferrel.sync().cases)

        self.ferrel.post_changes(CaseBlock(
            create=True,
            case_id=mother_id,
            date_modified=time,
            user_id=self.ferrel.user_id,
            case_type=PARENT_TYPE,
        ))

        # the original user should not get the parent case
        self.assertNotIn(mother_id, self.guy.sync().cases)

        # update the original case from another, adding an indexed case
        self.ferrel.post_changes(CaseBlock(
            case_id=case_id,
            user_id=self.ferrel.user_id,
            owner_id=self.guy.user_id,
            index={'mother': ('mother', mother_id)}
        ))

        # original user syncs again
        gsync = self.guy.sync()
        # make sure index updates take and indexed case also syncs
        mother = gsync.cases[mother_id]
        self.assertEqual(mother.case_type, PARENT_TYPE)
        self.assertEqual(mother.date_modified, time)
        self.assertEqual(mother.user_id, self.ferrel.user_id)
        self.assertEqual(mother.owner_id, self.ferrel.user_id)
        self.assertEqual(gsync.cases[case_id].index["mother"].case_id, mother_id)

    def testMultiUserEdits(self):
        time = datetime.utcnow()
        case_id = "multi_user_edits"

        # create a case from one user
        self.guy.change_cases(
            create=True,
            case_id=case_id,
            owner_id=self.shared_group._id,
            user_id=self.user.user_id,
            date_modified=time
        )

        # both users syncs
        self.guy.sync()
        self.ferrel.sync()

        # update case from same user
        self.guy.post_changes(CaseBlock(
            date_modified=time,
            case_id=case_id,
            user_id=self.user_id,
            update={'greeting': 'hello'}
        ))

        # update from another user
        self.ferrel.post_changes(CaseBlock(
            date_modified=time,
            case_id=case_id,
            user_id=self.user_id,
            update={'greeting_2': 'hello'}
        ))

        # make sure updates both appear
        joint_change = {
            'greeting': 'hello',
            'greeting_2': 'hello',
        }
        self.assertEqual(self.guy.sync().cases[case_id].update, joint_change)
        self.assertEqual(self.ferrel.sync().cases[case_id].update, joint_change)

    def testOtherUserCloses(self):
        # create a case from one user
        case_id = "other_user_closes"
        self.guy.post_changes(create=True, case_id=case_id)

        # sync then close case from another user
        self.ferrel.post_changes(CaseBlock(
            case_id=case_id,
            user_id=self.user_id,
            close=True
        ))

        # original user syncs again; make sure close block appears
        self.assertIn(case_id, self.guy.sync().cases)

        # make sure closed cases don't show up in the next sync log
        self.assertNotIn(case_id, self.guy.sync().cases)

    def testOtherUserUpdatesUnowned(self):
        # create a case from one user and assign ownership elsewhere
        case_id = "other_user_updates_unowned"
        self.guy.post_changes(
            create=True,
            case_id=case_id,
            owner_id=self.ferrel.user_id,
        )

        # sync and update from another user
        fsync = self.ferrel.sync()
        self.assertIn(case_id, fsync.cases)

        self.ferrel.post_changes(CaseBlock(
            case_id=case_id,
            user_id=self.ferrel.user_id,
            update={'greeting': 'hello'},
        ))

        # original user syncs again; make sure there are no new changes
        self.assertNotIn(case_id, self.guy.sync().cases)

    def testIndexesSync(self):
        # create a parent and child case (with index) from one user
        parent_id = "indexes_sync_parent"
        case_id = "indexes_sync"
        self.guy.change_cases(
            create=True,
            case_id=parent_id,
            owner_id=self.user_id,
        )
        self.guy.post_changes(CaseBlock(
            create=True,
            case_id=case_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            index={'mother': ('mother', parent_id)}
        ))

        # make sure the second user doesn't get either
        fsync = self.ferrel.sync()
        self.assertNotIn(case_id, fsync.cases)
        self.assertNotIn(parent_id, fsync.cases)

        # assign just the child case to a second user
        self.guy.post_changes(CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.user_id,
            owner_id=self.ferrel.user_id,
            update={"greeting": "hello"}
        ))

        # second user syncs; make sure both cases restore
        fsync = self.ferrel.sync()
        self.assertIn(case_id, fsync.cases)
        self.assertIn(parent_id, fsync.cases)

    def testOtherUserUpdatesIndex(self):
        # create a parent and child case (with index) from one user
        parent_id = "other_updates_index_parent"
        case_id = "other_updates_index_child"
        self.guy.change_cases(case_id=parent_id, create=True)
        self.guy.sync()

        self.guy.change_cases(CaseBlock(
            create=True,
            case_id=case_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            index={'mother': ('mother', parent_id)}
        ))
        gsync = self.guy.sync()
        self.assertNotIn(case_id, gsync.cases)
        self.assertNotIn(parent_id, gsync.cases)

        # assign the parent case away from same user
        self.guy.change_cases(CaseBlock(
            case_id=parent_id,
            user_id=self.user_id,
            owner_id=self.ferrel.user_id,
            update={"greeting": "hello"}
        ))
        gsync = self.guy.sync()

        # these tests added to debug another issue revealed by this test
        self.assertIn(case_id, gsync.log.case_ids_on_phone)
        self.assertIn(parent_id, gsync.log.case_ids_on_phone)

        # make sure the other user gets the reassigned case
        self.assertIn(parent_id, self.ferrel.sync().cases)
        # update the parent case from another user
        self.ferrel.post_changes(CaseBlock(
            case_id=parent_id,
            user_id=self.ferrel.user_id,
            update={"greeting2": "hi"},
        ))

        # make sure the indexed case syncs again
        self.assertIn(parent_id, self.guy.sync().cases)

    def testOtherUserReassignsIndexed(self):
        # create a parent and child case (with index) from one user
        # assign the parent case away from the same user
        parent_id = "other_reassigns_index_parent"
        case_id = "other_reassigns_index_child"
        self.device.post_changes([
            CaseStructure(
                case_id=case_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={
                        'create': True,
                        'owner_id': self.ferrel.user_id,
                        'update': {"greeting": "hello"},
                    }),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
        # sync cases to second user
        self.ferrel.sync()
        gsync = self.guy.sync()
        self.assertIn(case_id, gsync.cases)
        self.assertIn(parent_id, gsync.cases)

        # change the child's owner from another user
        # also change the parent from the second user
        child_reassignment = CaseBlock(
            case_id=case_id,
            user_id=self.ferrel.user_id,
            owner_id=self.ferrel.user_id,
            update={"childgreeting": "hi!"},
        )
        other_parent_update = CaseBlock(
            case_id=parent_id,
            user_id=self.ferrel.user_id,
            owner_id=self.ferrel.user_id,
            update={"other_greeting": "something new"},
        )
        self.ferrel.post_changes([child_reassignment, other_parent_update])

        # at this point both cases are assigned to the other user so the
        # original user should not have them. however, the first sync should
        # send them down (with new ownership) so that they can be purged.

        # original user syncs again
        gsync = self.guy.sync()
        self.assertEqual(gsync.cases[parent_id].update["other_greeting"], "something new")
        self.assertEqual(gsync.cases[case_id].update, {"childgreeting": "hi!"})
        # also check that they are not sent to the phone on next sync
        gsync = self.guy.sync()
        self.assertNotIn(case_id, gsync.cases)
        self.assertNotIn(parent_id, gsync.cases)

        # change the parent again from the second user
        self.ferrel.post_changes(CaseBlock(
            case_id=parent_id,
            user_id=self.ferrel.user_id,
            owner_id=self.ferrel.user_id,
            update={"other_greeting": "something different"},
        ))

        # original user syncs again; should be no changes
        self.assertFalse(self.guy.sync().cases)

        # change the child again from the second user
        self.ferrel.post_changes(CaseBlock(
            case_id=case_id,
            user_id=self.ferrel.user_id,
            owner_id=self.ferrel.user_id,
            update={"childgreeting": "hi changed!"},
        ))

        # original user syncs again; should be no changes
        self.assertFalse(self.guy.sync().cases)

        # change owner of child back to orginal user from second user
        self.ferrel.post_changes(CaseBlock(
            case_id=case_id,
            user_id=self.ferrel.user_id,
            owner_id=self.user.user_id,
        ))

        # original user syncs again
        gsync = self.guy.sync()
        self.assertEqual(gsync.cases[parent_id].update["other_greeting"], "something different")
        self.assertEqual(gsync.cases[case_id].update, {"childgreeting": "hi changed!"})

    def testComplicatedGatesBug(self):
        # found this bug in the wild, used the real (test) forms to fix it
        # just running through this test used to fail hard, even though there
        # are no asserts
        folder_path = os.path.join(os.path.dirname(__file__),
            "data", "bugs", "dependent_case_conflicts")
        token = self.guy.sync().log._id
        for f in ["reg1.xml", "reg2.xml", "cf.xml", "close.xml"]:
            with open(os.path.join(folder_path, f), "rb") as fh:
                xml_data = fh.read()
            form = submit_form_locally(
                xml_data, 'test-domain', last_sync_token=token).xform
            self.assertFalse(hasattr(form, "problem") and form.problem)
            token = self.guy.sync().log._id

    def test_dependent_case_becomes_relevant_at_sync_time(self):
        """
        Make a case that is only relevant through a dependency.
        Then update it to be actually relevant.
        Make sure the sync removes it from the dependent list.
        """
        # create a parent and child case (with index) from one user
        parent_id, child_id = [uuid.uuid4().hex for i in range(2)]
        self.guy.post_changes([
            CaseStructure(
                case_id=child_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(
                        case_id=parent_id,
                        attrs={'create': True, 'owner_id': uuid.uuid4().hex},
                    ),
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
        sync_log = self.guy.last_sync.get_log()
        self._testUpdate(sync_log._id, {child_id: [index_ref]}, {parent_id: []})

        # have another user modify the owner ID of the dependent case to be the shared ID
        self.ferrel.post_changes(case_id=parent_id)
        gsync = self.guy.sync()
        self._testUpdate(gsync.log._id, {child_id: [index_ref], parent_id: []})

    def test_index_tree_conflict_handling(self):
        """
        Test that if another user changes the index tree, the original user
        gets the appropriate index tree update after sync.
        """
        # create a parent and child case (with index) from one user
        mom_id, dad_id, child_id = [uuid.uuid4().hex for i in range(3)]
        self.guy.post_changes([
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
        self._testUpdate(self.guy.last_sync.log._id, {
            child_id: [mom_ref, dad_ref],
            mom_id: [],
            dad_id: [],
        })

        # have another user modify the index ID of one of the cases
        new_mom_id = uuid.uuid4().hex
        self.ferrel.post_changes(
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
        )
        new_mom_ref = CommCareCaseIndex(identifier='mom', referenced_type='mom', referenced_id=new_mom_id)
        self._testUpdate(self.guy.sync().log._id, {
            child_id: [new_mom_ref, dad_ref],
            mom_id: [],
            dad_id: [],
            new_mom_id: [],
        })

    def test_incremental_sync_with_close_and_create(self):
        def create_case_graph(num):
            person = CaseStructure(
                case_id='person-%s' % num,
                attrs={'create': True, 'owner_id': self.shared_group._id},
            )
            occurrence = CaseStructure(
                case_id="occurrence-%s" % num,
                attrs={'create': True, 'owner_id': None},
                indices=[
                    CaseIndex(
                        person,
                        relationship='extension',
                        related_type='person',
                        identifier='person-index',
                    ),
                ],
            )
            episode = CaseStructure(
                case_id='episode-%s' % num,
                attrs={'create': True, 'owner_id': None},
                indices=[
                    CaseIndex(
                        occurrence,
                        relationship='extension',
                        related_type='occurrence',
                        identifier='occurrence-index',
                    ),
                ],
            )
            self.device.post_changes([episode])
            return person, occurrence, episode

        p1, o1, e1 = create_case_graph(1)
        p2, o2, e2 = create_case_graph(2)

        # Alice and Bob sync
        alice = self.get_device(sync=True)
        bob = self.get_device(user=self.other_user, sync=True)
        all_cases = {case.case_id for case in [p1, o1, e1, p2, o2, e2]}
        self.assertEqual(set(alice.last_sync.log.case_ids_on_phone), all_cases)
        self.assertEqual(set(bob.last_sync.log.case_ids_on_phone), all_cases)

        close_e1 = CaseBlock(
            create=False,
            case_id=e1.case_id,
            user_id=bob.user_id,
            owner_id=None,
            close=True,
        )
        e3 = CaseBlock(
            create=True,
            case_id='episode-3',
            user_id=bob.user_id,
            owner_id=None,
            index={'occurrence-index': ('occurrence', o1.case_id, 'extension')},
        )
        bob.change_cases([close_e1, e3])
        bob.sync()

        a1 = CaseBlock(
            create=True,
            case_id='adherence-1',
            user_id=alice.user_id,
            index={'episode-index': ('episode', e2.case_id, 'extension')},
        )
        alice.change_cases([a1])
        alice_cases = {case.case_id for case in [p1, o1, e3, p2, o2, e2, a1]}

        sync2 = alice.sync()
        self.assertEqual(set(sync2.log.case_ids_on_phone), alice_cases)
        self.assertEqual(set(sync2.cases), {e1.case_id, e3.case_id})

        sync3 = alice.sync()
        self.assertEqual(set(sync3.log.case_ids_on_phone), alice_cases)
        self.assertEqual(set(sync3.cases), set())


@use_sql_backend
class MultiUserSyncTestSQL(MultiUserSyncTest):
    pass


class LiveQueryMultiUserSyncTest(MultiUserSyncTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryMultiUserSyncTestSQL(LiveQueryMultiUserSyncTest):
    pass


class SteadyStateExtensionSyncTest(BaseSyncTest):
    """
    Test that doing multiple clean syncs with extensions does what we think it will
    """

    @classmethod
    def setUpClass(cls):
        super(SteadyStateExtensionSyncTest, cls).setUpClass()
        cls.other_user = create_restore_user(
            cls.project.name,
            username=OTHER_USERNAME,
        )
        cls._create_ownership_cleanliness(cls.user_id)
        cls._create_ownership_cleanliness(cls.other_user.user_id)

    @classmethod
    def _create_ownership_cleanliness(cls, user_id):
        OwnershipCleanlinessFlag.objects.get_or_create(
            owner_id=user_id,
            domain=cls.project.name,
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
        self.device.change_cases(extension)
        self.device.sync()
        return host, extension

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_delegating_extensions(self):
        """Make an extension, delegate it, send it back, see what happens"""
        guy = self.get_device()
        ferrel = self.get_device(user=self.other_user)
        host, extension = self._create_extension()

        # Make sure we get it
        self.assertIn(host.case_id, guy.sync().cases)
        # But ferrel doesn't
        self.assertNotIn(host.case_id, ferrel.sync().cases)

        # Reassign the extension to ferrel
        self.device.post_changes(case_id=extension.case_id, owner_id=ferrel.user_id)

        # other user should sync the host
        self.assertIn(host.case_id, ferrel.sync().cases)

        # original user should sync the extension because it has changed
        # but not the host, because that didn't
        self.assertEqual(set(guy.sync().cases), {extension.case_id})

        # syncing again by original user should not pull anything
        self.assertFalse(guy.sync().cases)

        # reassign the extension case
        self.device.post_changes(case_id=extension.case_id, owner_id='-')

        # make sure other_user gets it because it changed
        self.assertIn(extension.case_id, ferrel.sync().cases)
        # first user should also get it since it was updated
        self.assertIn(extension.case_id, guy.sync().cases)

        # other user syncs again, should not get the extension
        self.assertNotIn(extension.case_id, ferrel.sync().cases)

        # Hooray!

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_multiple_syncs(self):
        guy = self.get_device()
        host, extension = self._create_extension()
        both_ids = {host.case_id, extension.case_id}

        # NOTE for clean_owners sync it is important that this is the
        # first sync for this device. In other words, the restore state
        # must not have a last sync log. This is possibly due to a bug
        # in the clean_owners sync implementation, which omits extension
        # cases that have been created since the last sync because they
        # are not in last_sync_log.extension_index_tree. See
        # _get_case_ids_for_owners_with_extensions after the comment "we
        # also need to fetch unowned extension cases that have been
        # modified". This comment can be removed when
        # test_two_device_extension_sync_bug is no longer skipped for
        # clean_owners.
        sync0 = guy.sync()
        self.assertEqual(sync0.log.case_ids_on_phone, both_ids)
        self.assertEqual(set(sync0.cases), both_ids)

        sync1 = guy.sync()
        self.assertEqual(sync1.log.case_ids_on_phone, both_ids)
        self.assertFalse(sync1.cases)

        sync2 = guy.sync()
        self.assertEqual(sync2.log.case_ids_on_phone, both_ids)
        self.assertFalse(sync2.cases)

        sync3 = guy.sync()
        self.assertEqual(sync3.log.case_ids_on_phone, both_ids)
        self.assertFalse(sync3.cases)

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_two_device_extension_sync_bug(self):
        if self.restore_options["case_sync"] == CLEAN_OWNERS:
            self.skipTest("a bug in clean_owners causes this to fail")
            # not going after this now since livequery passes
        deviceA = self.get_device(user=self.other_user, sync=True)
        deviceB = self.get_device(user=self.other_user, sync=True)
        self.assertFalse(deviceA.last_sync.cases)
        self.assertFalse(deviceB.last_sync.cases)

        host = CaseStructure(case_id='host', attrs={'create': True})
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
        both_ids = {host.case_id, extension.case_id}
        deviceA.change_cases(extension)
        syncA = deviceA.sync()
        self.assertEqual(syncA.log.case_ids_on_phone, both_ids)
        self.assertFalse(syncA.cases)

        sync0 = deviceB.sync()
        self.assertEqual(sync0.log.case_ids_on_phone, both_ids)
        self.assertEqual(set(sync0.cases), both_ids)

        sync1 = deviceB.sync()
        self.assertEqual(sync1.log.case_ids_on_phone, both_ids)
        self.assertFalse(sync1.cases)


@use_sql_backend
class SteadyStateExtensionSyncTestSQL(SteadyStateExtensionSyncTest):
    pass


class LiveQuerySteadyStateExtensionSyncTest(SteadyStateExtensionSyncTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySteadyStateExtensionSyncTestSQL(LiveQuerySteadyStateExtensionSyncTest):
    pass


class SyncTokenReprocessingTest(BaseSyncTest):
    """
    Tests sync token logic for fixing itself when it gets into a bad state.
    """

    def testShouldHaveCase(self):
        case_id = "should_have"
        self.device.post_changes(case_id=case_id, create=True)
        sync_log = self.device.last_sync.get_log()
        cases_on_phone = sync_log.tests_only_get_cases_on_phone()
        self.assertEqual({case_id}, {c.case_id for c in cases_on_phone})

        # manually delete it and then try to update
        sync_log.test_only_clear_cases_on_phone()
        sync_log.save()

        self.device.post_changes(CaseBlock(
            case_id=case_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type=PARENT_TYPE,
            update={'something': "changed"},
        ))
        # this should work because it should magically fix itself
        sync_log = self.device.last_sync.get_log()
        self.assertFalse(getattr(sync_log, 'has_assert_errors', False))


@use_sql_backend
class SyncTokenReprocessingTestSQL(SyncTokenReprocessingTest):
    pass


class LiveQuerySyncTokenReprocessingTest(SyncTokenReprocessingTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySyncTokenReprocessingTestSQL(LiveQuerySyncTokenReprocessingTest):
    pass


class LooseSyncTokenValidationTest(BaseSyncTest):

    def test_submission_with_bad_log_toggle_enabled(self):
        # this is just asserting that an exception is not raised when there's no synclog
        post_case_blocks(
            [CaseBlock(create=True, case_id='bad-log-toggle-enabled').as_xml()],
            form_extras={"last_sync_token": 'not-a-valid-synclog-id'},
            domain='submission-domain-with-toggle',
        )

    def test_restore_with_bad_log_toggle_enabled(self):
        with self.assertRaises(RestoreException):
            RestoreConfig(
                project=Domain(name='restore-domain-with-toggle'),
                restore_user=self.user,
                params=RestoreParams(
                    version=V2,
                    sync_log_id='not-a-valid-synclog-id',
                ),
                **self.restore_options
            ).get_payload()


@use_sql_backend
class LooseSyncTokenValidationTestSQL(LooseSyncTokenValidationTest):
    pass


class LiveQueryLooseSyncTokenValidationTest(LooseSyncTokenValidationTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryLooseSyncTokenValidationTestSQL(LiveQueryLooseSyncTokenValidationTest):
    pass


class IndexSyncTest(BaseSyncTest):

    def test_sync_index_between_open_owned_cases(self):
        child_id = "leaf"
        parent_id = "branch"
        other_parent_id = "sky"
        branch_index = 'stem_index'
        wave_index = 'wave_index'
        self.device.change_cases(CaseStructure(
            case_id=child_id,
            attrs={'create': True},
            indices=[CaseIndex(
                CaseStructure(case_id=parent_id, attrs={'create': True}),
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
                identifier=branch_index,
            ), CaseIndex(
                CaseStructure(
                    case_id=other_parent_id,
                    attrs={'create': True, 'owner_id': 'someone-else'},
                ),
                relationship=CHILD_RELATIONSHIP,
                related_type=PARENT_TYPE,
                identifier=wave_index,
            )],
        ))
        sync = self.device.sync(restore_id='')
        self.assertEqual(set(sync.cases), {child_id, parent_id, other_parent_id})
        self.assertIn(branch_index, sync.cases[child_id].index)
        self.assertIn(wave_index, sync.cases[child_id].index)


@use_sql_backend
class IndexSyncTestSQL(IndexSyncTest):
    pass


class LiveQueryIndexSyncTest(IndexSyncTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryIndexSyncTestSQL(LiveQueryIndexSyncTest):
    pass
