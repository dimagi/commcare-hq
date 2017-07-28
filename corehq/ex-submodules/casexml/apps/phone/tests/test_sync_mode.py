import uuid
from xml.etree import ElementTree
from couchdbkit import ResourceNotFound
from django.test.utils import override_settings
from django.test import TestCase
import os

from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.exceptions import RestoreException
from casexml.apps.phone.tests.utils import (
    get_exactly_one_wrapped_sync_log,
    get_next_sync_log,
    generate_restore_payload,
    MockDevice,
)
from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure, CaseIndex
from casexml.apps.phone.tests.utils import synclog_from_restore_payload, get_restore_config
from casexml.apps.phone.models import OwnershipCleanlinessFlag
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    use_sql_backend,
)
from corehq.util.test_utils import flag_enabled
from casexml.apps.case.tests.util import (
    check_user_has_case, assert_user_doesnt_have_case,
    assert_user_has_case, TEST_DOMAIN_NAME, assert_user_has_cases,
    check_payload_has_case_ids, assert_user_doesnt_have_cases)
from casexml.apps.phone.tests.utils import create_restore_user, has_cached_payload
from casexml.apps.phone.models import (
    AbstractSyncLog,
    get_properly_wrapped_sync_log,
    LOG_FORMAT_LIVEQUERY,
    LOG_FORMAT_SIMPLIFIED,
    SimplifiedSyncLog,
    SyncLog,
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
from datetime import datetime

USERNAME = "syncguy"
OTHER_USERNAME = "ferrel"
PARENT_TYPE = "mother"
CHILD_RELATIONSHIP = "child"


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class SyncBaseTest(TestCase):
    """
    Shared functionality among tests
    """
    restore_options = {'case_sync': CLEAN_OWNERS}

    @classmethod
    def setUpClass(cls):
        super(SyncBaseTest, cls).setUpClass()
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
        super(SyncBaseTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases()
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_sync_logs()

        self.device = self.get_device()
        self.sync_log = self.device.sync(overwrite_cache=True, version=V1).log
        self.factory = self.device.case_factory
        # HACK remove once all tests are converted to use self.device
        # NOTE self.device.sync() overrides last_sync_token with the
        # most recent sync token, so this is effectively ignored when
        # using that method.
        self.factory.form_extras = {
            'last_sync_token': self.sync_log._id,
        }

    def tearDown(self):
        restore_config = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            **self.restore_options
        )
        restore_config.cache.delete(restore_config._restore_cache_key)
        super(SyncBaseTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        super(SyncBaseTest, cls).tearDownClass()

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
        return submit_form_locally(xml_data, 'test-domain', last_sync_token=token_id).xform

    def get_device(self, **kw):
        kw.setdefault("project", self.project)
        kw.setdefault("user", self.user)
        kw.setdefault("restore_options", self.restore_options)
        kw.setdefault("default_case_type", PARENT_TYPE)
        return MockDevice(**kw)

    def _postFakeWithSyncToken(self, caseblocks, token_id):
        if not isinstance(caseblocks, list):
            # can't use list(caseblocks) since that returns children of the node
            # http://lxml.de/tutorial.html#elements-are-lists
            caseblocks = [caseblocks]
        return self.factory.post_case_blocks(caseblocks, form_extras={"last_sync_token": token_id})

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

    def get_next_sync_log(self, **kw):
        assert not set(self.restore_options) & set(kw), kw
        kw.update(self.restore_options)
        kw.setdefault('project', self.project)
        kw.setdefault('user', self.user)
        return get_next_sync_log(**kw)


class SyncTokenUpdateTest(SyncBaseTest):
    """
    Tests sync token updates on submission related to the list of cases
    on the phone and the footprint.
    """

    def testInitialEmpty(self):
        """
        Tests that a newly created sync token has no cases attached to it.
        """
        sync_log = get_exactly_one_wrapped_sync_log()
        self._testUpdate(sync_log.get_id, {}, {})

    def testOwnUpdatesDontSync(self):
        case_id = "own_updates_dont_sync"
        self._createCaseStubs([case_id])
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        self.factory.create_or_update_case(
            CaseStructure(case_id=case_id, attrs={'update': {"greeting": "hello"}}),
        )
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        self.factory.create_or_update_case(
            CaseStructure(case_id=case_id, attrs={'owner_id': 'do-not-own-this'}),
        )
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

    def test_change_index_type(self):
        """
        Test that changing an index type updates the sync log
        """
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # update the child's index (parent type)
        updated_type = "updated_type"
        child = CaseBlock(
            create=False, case_id=child_id, user_id=self.user_id,
            index={index_id: (updated_type, parent_id)},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        parent_ref.referenced_type = updated_type
        self._testUpdate(self.sync_log.get_id, {parent_id: [],
                                                child_id: [parent_ref]})

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

    def test_delete_only_index(self):
        child_id, parent_id, index_id, parent_ref = self._initialize_parent_child()
        # delete the first index
        child = CaseBlock(create=False, case_id=child_id, user_id=self.user_id,
                          index={index_id: (PARENT_TYPE, "")},
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)
        self._testUpdate(self.sync_log.get_id, {parent_id: [], child_id: []})

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
        child = CaseBlock(create=False, case_id=child_id, user_id=self.user_id,
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
        close = CaseBlock(create=False, case_id=parent_id, user_id=self.user_id, close=True).as_xml()
        self._postFakeWithSyncToken(close, self.sync_log.get_id)
        self._testUpdate(self.sync_log.get_id, {child_id: [index_ref]},
                         {parent_id: []})

        # try a clean restore again
        assert_user_has_cases(self, self.user, [parent_id, child_id])

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
            CaseBlock(create=False, case_id=child_id, user_id=self.user_id, owner_id=new_owner).as_xml(),
            self.sync_log.get_id
        )

        # child should be moved, parent should still be there
        self._testUpdate(self.sync_log.get_id, {parent_id: []}, {})

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
            user_id=self.user_id,
            update={"greeting": "hello"}
        ).as_xml()
        form, _ = self._postFakeWithSyncToken(update_block, self.sync_log.get_id)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=self.sync_log.get_id)

        form.archive()
        assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id, purge_restore_cache=True)

    def testUserLoggedIntoMultipleDevices(self):
        # test that a child case created by the same user from a different device
        # gets included in the sync

        parent_id = "parent"
        child_id = "child"
        self._createCaseStubs([parent_id])

        # create child case using a different sync log ID
        other_sync_log = self.get_next_sync_log(version="2.0")
        child = CaseBlock(
            create=True,
            case_id=child_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            index={'mother': ('mother', parent_id)}
        ).as_xml()
        self._postFakeWithSyncToken(child, other_sync_log.get_id)

        # ensure child case is included in sync using original sync log ID
        assert_user_has_case(self, self.user, child_id, restore_id=self.sync_log.get_id)

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

    def test_closed_case_not_in_next_sync(self):
        # create a case
        case_id = self.factory.create_case().case_id
        # sync
        restore_config = RestoreConfig(
            project=Domain(name=self.project.name),
            restore_user=self.user,
            params=RestoreParams(self.sync_log._id, version=V2),
            **self.restore_options
        )
        next_sync = synclog_from_restore_payload(restore_config.get_payload().as_string())
        self.assertTrue(next_sync.phone_is_holding_case(case_id))
        # close the case on the second sync
        self.factory.create_or_update_case(CaseStructure(case_id=case_id, attrs={'close': True}),
                                           form_extras={'last_sync_token': next_sync._id})
        # sync again
        restore_config = RestoreConfig(
            project=Domain(name=self.project.name),
            restore_user=self.user, params=RestoreParams(next_sync._id, version=V2),
            **self.restore_options
        )
        last_sync = synclog_from_restore_payload(restore_config.get_payload().as_string())
        self.assertFalse(last_sync.phone_is_holding_case(case_id))

    def test_sync_by_user_id(self):
        # create a case with an empty owner but valid user id
        case_id = self.factory.create_case(owner_id='', user_id=self.user_id).case_id
        restore_config = RestoreConfig(
            self.project, restore_user=self.user, **self.restore_options)
        payload = restore_config.get_payload().as_string()
        self.assertTrue(case_id in payload)
        sync_log = synclog_from_restore_payload(payload)
        self.assertTrue(sync_log.phone_is_holding_case(case_id))

    def test_create_irrelevant_owner_and_update_to_irrelevant_owner_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        self.factory.create_case(owner_id='irrelevant_1', update={'owner_id': 'irrelevant_2'}, strict=False)

    def test_create_irrelevant_owner_and_update_to_relevant_owner_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        case = self.factory.create_case(owner_id='irrelevant_1', update={'owner_id': self.user_id}, strict=False)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        # todo: this bug isn't fixed on old sync. This check is a hack due to the inability to
        # override the setting on a per-test level and should be removed when the new
        # sync is fully rolled out.
        if isinstance(sync_log, SimplifiedSyncLog):
            self.assertTrue(sync_log.phone_is_holding_case(case.case_id))

    def test_create_relevant_owner_and_update_to_empty_owner_in_same_form(self):
        case = self.factory.create_case(owner_id=self.user_id, update={'owner_id': ''}, strict=False)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        if isinstance(sync_log, SimplifiedSyncLog):
            self.assertFalse(sync_log.phone_is_holding_case(case.case_id))

    def test_create_irrelevant_owner_and_update_to_empty_owner_in_same_form(self):
        case = self.factory.create_case(owner_id='irrelevant_1', update={'owner_id': ''}, strict=False)
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertFalse(sync_log.phone_is_holding_case(case.case_id))

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

    def test_create_irrelevant_owner_and_close_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        self.factory.create_case(owner_id='irrelevant_1', close=True)

    def test_reassign_and_close_in_same_form(self):
        # this tests an edge case that used to crash on submission which is why there are no asserts
        case_id = self.factory.create_case().case_id
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=case_id,
                attrs={'owner_id': 'irrelevant', 'close': True},
            )
        )

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

        self.factory.create_or_update_cases([child])

        self._testUpdate(
            self.sync_log._id,
            {child.case_id: [parent_ref],
             parent.case_id: [grandparent_ref],
             grandparent.case_id: []},
            {parent.case_id: [grandparent.case_id],
             grandparent.case_id: []}
        )

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
        next_sync_log = self.get_next_sync_log(restore_id=self.sync_log._id, version=V2)
        assert_user_doesnt_have_case(self, self.user, case.case_id, restore_id=next_sync_log._id)

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
        self.factory.create_or_update_cases([grandparent, parent_1, parent_2, child_1, child_2])
        assert_user_has_cases(self, self.user, [
            grandparent.case_id,
            parent_1.case_id,
            parent_2.case_id,
            child_1.case_id,
            child_2.case_id
        ])


@use_sql_backend
class SyncTokenUpdateTestSQL(SyncTokenUpdateTest):
    pass


class LiveQuerySyncTokenUpdateTest(SyncTokenUpdateTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySyncTokenUpdateTestSQL(LiveQuerySyncTokenUpdateTest):
    pass


class SyncDeletedCasesTest(SyncBaseTest):

    def test_deleted_case_doesnt_sync(self):
        case = self.factory.create_case()
        case.soft_delete()
        assert_user_doesnt_have_case(self, self.user, case.case_id)

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
                    CaseStructure(case_id=parent_id, attrs={'create': True}),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                )],
            )
        ])
        CaseAccessors().get_case(parent_id).soft_delete()
        assert_user_doesnt_have_case(self, self.user, parent_id)
        # todo: in the future we may also want to purge the child
        assert_user_has_case(self, self.user, child_id)


@use_sql_backend
class SyncDeletedCasesTestSQL(SyncDeletedCasesTest):
    pass


class LiveQuerySyncDeletedCasesTest(SyncDeletedCasesTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySyncDeletedCasesTestSQL(LiveQuerySyncDeletedCasesTest):
    pass


class ExtensionCasesSyncTokenUpdates(SyncBaseTest):
    """Makes sure the extension case trees are propertly updated
    """

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


@use_sql_backend
class ExtensionCasesSyncTokenUpdatesSQL(ExtensionCasesSyncTokenUpdates):
    pass


class LiveQueryExtensionCasesSyncTokenUpdates(ExtensionCasesSyncTokenUpdates):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryExtensionCasesSyncTokenUpdatesSQL(LiveQueryExtensionCasesSyncTokenUpdates):
    pass


class ExtensionCasesFirstSync(SyncBaseTest):

    def setUp(self):
        super(ExtensionCasesFirstSync, self).setUp()
        self.restore_config = RestoreConfig(
            project=self.project, restore_user=self.user, **self.restore_options)
        self.restore_state = self.restore_config.restore_state

    def test_is_first_extension_sync(self):
        """Before any syncs, this should return true when the toggle is enabled, otherwise false"""
        with flag_enabled('EXTENSION_CASES_SYNC_ENABLED'):
            self.assertTrue(self.restore_state.is_first_extension_sync)

        self.assertFalse(self.restore_state.is_first_extension_sync)

    def test_is_first_extension_sync_after_sync(self):
        """After a sync with the extension code in place, this should be false"""
        self.factory.create_case()
        with flag_enabled('EXTENSION_CASES_SYNC_ENABLED'):
            config = get_restore_config(self.project, self.user,
                restore_id=self.sync_log._id, **self.restore_options)
            self.assertTrue(get_properly_wrapped_sync_log(self.sync_log._id).extensions_checked)
            self.assertFalse(config.restore_state.is_first_extension_sync)

        config = get_restore_config(self.project, self.user,
            restore_id=self.sync_log._id, **self.restore_options)
        self.assertTrue(get_properly_wrapped_sync_log(self.sync_log._id).extensions_checked)
        self.assertFalse(config.restore_state.is_first_extension_sync)


@use_sql_backend
class ExtensionCasesFirstSyncSQL(ExtensionCasesFirstSync):
    pass


class LiveQueryExtensionCasesFirstSync(ExtensionCasesFirstSync):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryExtensionCasesFirstSyncSQL(LiveQueryExtensionCasesFirstSync):
    pass


class ChangingOwnershipTest(SyncBaseTest):

    def setUp(self):
        super(ChangingOwnershipTest, self).setUp()

    def test_remove_user_from_group(self):
        group = Group(
            domain=self.project.name,
            name='remove_user',
            case_sharing=True,
            users=[self.user.user_id]
        )
        group.save()
        initial_sync_log = self.get_next_sync_log()
        self.assertTrue(group._id in initial_sync_log.owner_ids_on_phone)

        # since we got a new sync log, have to update the factory as well
        self.factory.form_extras = {'last_sync_token': initial_sync_log._id}

        # create a case owned by the group
        case_id = self.factory.create_case(owner_id=group._id).case_id
        # make sure it's there
        sync_log = get_properly_wrapped_sync_log(initial_sync_log._id)
        self.assertTrue(sync_log.phone_is_holding_case(case_id))

        # make sure it's there on new sync
        incremental_sync_log = self._get_incremental_synclog_for_user(self.user, since=initial_sync_log._id)
        self.assertTrue(group._id in incremental_sync_log.owner_ids_on_phone)
        self.assertTrue(incremental_sync_log.phone_is_holding_case(case_id))

        # remove the owner id and confirm that owner and case are removed on next sync
        group.remove_user(self.user.user_id)
        group.save()
        incremental_sync_log = self._get_incremental_synclog_for_user(self.user, since=incremental_sync_log._id)
        self.assertFalse(group._id in incremental_sync_log.owner_ids_on_phone)
        self.assertFalse(incremental_sync_log.phone_is_holding_case(case_id))

    def test_add_user_to_group(self):
        group = Group(
            domain=self.project.name,
            name='add_user',
            case_sharing=True,
            users=[]
        )
        group.save()
        # create a case owned by the group
        case_id = self.factory.create_case(owner_id=group._id).case_id
        # shouldn't be there
        initial_sync_log = self.get_next_sync_log()
        self.assertFalse(initial_sync_log.phone_is_holding_case(case_id))

        group.add_user(self.user.user_id)
        # make sure it's there on new sync
        incremental_sync_log = self._get_incremental_synclog_for_user(self.user, since=initial_sync_log._id)
        self.assertTrue(group._id in incremental_sync_log.owner_ids_on_phone)
        self.assertTrue(incremental_sync_log.phone_is_holding_case(case_id))

    def _get_incremental_synclog_for_user(self, user, since):
        incremental_restore_config = RestoreConfig(
            self.project,
            restore_user=user,
            params=RestoreParams(version=V2, sync_log_id=since),
            **self.restore_options
        )
        return synclog_from_restore_payload(incremental_restore_config.get_payload().as_string())


@use_sql_backend
class ChangingOwnershipTestSQL(ChangingOwnershipTest):
    pass


class LiveQueryChangingOwnershipTest(ChangingOwnershipTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryChangingOwnershipTestSQL(LiveQueryChangingOwnershipTest):
    pass


class SyncTokenCachingTest(SyncBaseTest):

    def testCaching(self):
        self.assertFalse(has_cached_payload(self.sync_log, V2))
        # first request should populate the cache
        original_payload = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
            **self.restore_options
        ).get_payload().as_string()
        next_sync_log = synclog_from_restore_payload(original_payload)

        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(has_cached_payload(self.sync_log, V2))

        # a second request with the same config should be exactly the same
        cached_payload = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
            **self.restore_options
        ).get_payload().as_string()
        self.assertEqual(original_payload, cached_payload)

        # caching a different version should also produce something new
        versioned_payload = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(
                version=V1,
                sync_log_id=self.sync_log._id,
            ),
            **self.restore_options
        ).get_payload().as_string()
        self.assertNotEqual(original_payload, versioned_payload)
        versioned_sync_log = synclog_from_restore_payload(versioned_payload)
        self.assertNotEqual(next_sync_log._id, versioned_sync_log._id)

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
        original_payload = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
            **self.restore_options
        ).get_payload().as_string()
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(has_cached_payload(self.sync_log, V2))

        # posting a case associated with this sync token should invalidate the cache
        case_id = "cache_invalidation"
        self._createCaseStubs([case_id])
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertFalse(has_cached_payload(SyncLog.get(self.sync_log._id), V2))

        # resyncing should recreate the cache
        next_payload = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
            **self.restore_options
        ).get_payload().as_string()
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(has_cached_payload(self.sync_log, V2))
        self.assertNotEqual(original_payload, next_payload)
        self.assertFalse(case_id in original_payload)
        # since it was our own update, it shouldn't be in the new payload either
        self.assertFalse(case_id in next_payload)
        # we can be explicit about why this is the case
        self.assertTrue(self.sync_log.phone_is_holding_case(case_id))

    def testCacheNonInvalidation(self):
        original_payload = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
            **self.restore_options
        ).get_payload().as_string()
        self.sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertTrue(has_cached_payload(self.sync_log, V2))

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
            restore_user=self.user,
            params=RestoreParams(
                version=V2,
                sync_log_id=self.sync_log._id,
            ),
            **self.restore_options
        ).get_payload().as_string()
        self.assertEqual(original_payload, next_payload)
        self.assertFalse(case_id in next_payload)

    def testCacheInvalidationAfterFileDelete(self):
        # first request should populate the cache
        original_payload = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            cache_settings=RestoreCacheSettings(force_cache=True),
            **self.restore_options
        ).get_payload()
        self.assertNotIsInstance(original_payload, CachedResponse)

        # Delete cached file
        os.remove(original_payload.get_filename())

        # resyncing should recreate the cache
        next_file = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            **self.restore_options
        ).get_payload()
        self.assertNotIsInstance(next_file, CachedResponse)
        self.assertNotEqual(original_payload.get_filename(), next_file.get_filename())


@use_sql_backend
class SyncTokenCachingTestSQL(SyncTokenCachingTest):
    pass


class LiveQuerySyncTokenCachingTest(SyncTokenCachingTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySyncTokenCachingTestSQL(LiveQuerySyncTokenCachingTest):
    pass


class MultiUserSyncTest(SyncBaseTest):
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
        cls.other_user_id = cls.other_user.user_id

        cls.shared_group = Group(
            domain=cls.project.name,
            name='shared_group',
            case_sharing=True,
            users=[cls.other_user.user_id, cls.user.user_id]
        )
        cls.shared_group.save()

    def setUp(self):
        super(MultiUserSyncTest, self).setUp()
        # this creates the initial blank sync token in the database
        self.other_sync_log = self.get_next_sync_log(user=self.other_user)

        self.sync_log = self.get_next_sync_log()
        # since we got a new sync log, have to update the factory as well
        self.factory.form_extras = {'last_sync_token': self.sync_log._id}
        self.factory.case_defaults.update({'owner_id': self.shared_group._id})

        self.assertTrue(self.shared_group._id in self.other_sync_log.owner_ids_on_phone)
        self.assertTrue(self.other_user_id in self.other_sync_log.owner_ids_on_phone)
        self.assertTrue(self.shared_group._id in self.sync_log.owner_ids_on_phone)
        self.assertTrue(self.user_id in self.sync_log.owner_ids_on_phone)

    def testSharedCase(self):
        # create a case by one user
        case_id = "shared_case"
        self._createCaseStubs([case_id], owner_id=self.shared_group._id)
        # should sync to the other owner
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

    def testOtherUserEdits(self):
        # create a case by one user
        case_id = "other_user_edits"
        self._createCaseStubs(
            [case_id],
            owner_id=self.shared_group._id
        )

        # sync to the other's phone to be able to edit
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

        latest_sync = SyncLog.last_for_user(self.other_user_id)
        # update from another
        self._postFakeWithSyncToken(
            CaseBlock(create=False, case_id=case_id, user_id=self.other_user_id,
                      update={'greeting': "Hello!"}
        ).as_xml(), latest_sync.get_id)

        # original user syncs again
        # make sure updates take
        _, match = assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        self.assertTrue("Hello!" in match.to_string())

    def testOtherUserAddsIndex(self):
        time = datetime.utcnow()

        # create a case from one user
        case_id = "other_user_adds_index"
        self._createCaseStubs(
            [case_id],
            owner_id=self.shared_group._id,
        )

        # sync to the other's phone to be able to edit
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

        latest_sync = SyncLog.last_for_user(self.other_user_id)
        mother_id = "other_user_adds_index_mother"

        parent_case = CaseBlock(
            create=True,
            date_modified=time,
            case_id=mother_id,
            user_id=self.other_user_id,
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
                user_id=self.other_user_id,
                owner_id=self.user_id,
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
            user_id=self.other_user_id,
            case_type=PARENT_TYPE,
            owner_id=self.other_user_id,
        ).as_xml()

        check_user_has_case(self, self.user, expected_parent_case,
                            restore_id=self.sync_log.get_id, purge_restore_cache=True)
        _, orig = assert_user_has_case(self, self.user, case_id, restore_id=self.sync_log.get_id)
        self.assertTrue("index" in orig.to_string())

    def testMultiUserEdits(self):
        time = datetime.utcnow()

        # create a case from one user
        case_id = "multi_user_edits"
        self._createCaseStubs(
            [case_id],
            owner_id=self.shared_group._id,
            user_id=self.user.user_id,
            date_modified=time
        )

        # both users syncs
        main_sync_log = self.get_next_sync_log()
        self.other_sync_log = self.get_next_sync_log(user=self.other_user)

        # update case from same user
        my_change = CaseBlock(
            create=False,
            date_modified=time,
            case_id=case_id,
            user_id=self.user_id,
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
            user_id=self.user_id,
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
            user_id=self.user_id,
            date_opened=time.date(),
            update={
                'greeting': 'hello',
                'greeting_2': 'hello'
            },
            owner_id=self.shared_group._id,
            case_name='',
            case_type='mother',
        ).as_xml()

        check_user_has_case(self, self.user, joint_change, restore_id=main_sync_log.get_id)
        check_user_has_case(self, self.other_user, joint_change, restore_id=self.other_sync_log.get_id)

    def testOtherUserCloses(self):
        # create a case from one user
        case_id = "other_user_closes"
        self._createCaseStubs([case_id], owner_id=self.shared_group._id)

        # sync then close case from another user
        other_sync_log = self.get_next_sync_log(user=self.other_user)
        close_block = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.user_id,
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
        next_synclog = self.get_next_sync_log(restore_id=self.sync_log._id)
        assert_user_doesnt_have_case(self, self.user, case_id, restore_id=next_synclog.get_id)

    def testOtherUserUpdatesUnowned(self):
        # create a case from one user and assign ownership elsewhere
        case_id = "other_user_updates_unowned"
        self._createCaseStubs([case_id], owner_id=self.other_user_id)

        # sync and update from another user
        assert_user_has_case(self, self.other_user, case_id, restore_id=self.other_sync_log.get_id)

        self.other_sync_log = SyncLog.last_for_user(self.other_user_id)
        update = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.other_user_id,
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
        self._createCaseStubs([parent_id], owner_id=self.user_id)
        child = CaseBlock(
            create=True,
            case_id=case_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            index={'mother': ('mother', parent_id)}
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)

        # make sure the second user doesn't get either
        assert_user_doesnt_have_cases(
            self, self.other_user, [case_id, parent_id], restore_id=self.other_sync_log.get_id
        )

        # assign just the child case to a second user
        child_update = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.user_id,
            owner_id=self.other_user_id,
            update={"greeting": "hello"}
        ).as_xml()
        self._postFakeWithSyncToken(child_update, self.sync_log.get_id)
        # second user syncs
        # make sure both cases restore
        assert_user_has_cases(
            self, self.other_user, [case_id, parent_id], restore_id=self.other_sync_log.get_id,
            purge_restore_cache=True
        )

    def testOtherUserUpdatesIndex(self):
        # create a parent and child case (with index) from one user
        parent_id = "other_updates_index_parent"
        case_id = "other_updates_index_child"
        self._createCaseStubs([parent_id], owner_id=self.shared_group._id)

        child = CaseBlock(
            create=True,
            case_id=case_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            index={'mother': ('mother', parent_id)}
        ).as_xml()
        self._postFakeWithSyncToken(child, self.sync_log.get_id)

        assert_user_doesnt_have_cases(self, self.user, [case_id, parent_id], restore_id=self.sync_log.get_id)

        # assign the parent case away from same user
        parent_update = CaseBlock(
            create=False,
            case_id=parent_id,
            user_id=self.user_id,
            owner_id=self.other_user_id,
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
        self.other_sync_log = SyncLog.last_for_user(self.other_user_id)
        other_parent_update = CaseBlock(
            create=False,
            case_id=parent_id,
            user_id=self.other_user_id,
            update={"greeting2": "hi"},
        ).as_xml()
        self._postFakeWithSyncToken(other_parent_update, self.other_sync_log.get_id)

        # make sure the indexed case syncs again
        latest_sync_log = SyncLog.last_for_user(self.user_id)
        assert_user_has_case(self, self.user, parent_id, restore_id=latest_sync_log.get_id,
                             purge_restore_cache=True)

    def testOtherUserReassignsIndexed(self):
        # create a parent and child case (with index) from one user
        # assign the parent case away from the same user
        parent_id = "other_reassigns_index_parent"
        case_id = "other_reassigns_index_child"
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=case_id,
                attrs={'create': True},
                indices=[CaseIndex(
                    CaseStructure(case_id=parent_id, attrs={
                        'create': True,
                        'owner_id': self.other_user_id,
                        'update': {"greeting": "hello"},
                    }),
                    relationship=CHILD_RELATIONSHIP,
                    related_type=PARENT_TYPE,
                )],
            )
        ])

        # sync cases to second user
        other_sync_log = self.get_next_sync_log(user=self.other_user)

        # change the child's owner from another user
        # also change the parent from the second user
        child_reassignment = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.other_user_id,
            owner_id=self.other_user_id,
            update={"childgreeting": "hi!"},
        ).as_xml()
        other_parent_update = CaseBlock(
            create=False,
            case_id=parent_id,
            user_id=self.other_user_id,
            owner_id=self.other_user_id,
            update={"other_greeting": "something new"}).as_xml()
        self._postFakeWithSyncToken([child_reassignment, other_parent_update], other_sync_log.get_id)

        latest_sync_log = SyncLog.last_for_user(self.user.user_id)
        self.assertEqual(latest_sync_log._id, self.sync_log._id)

        # at this point both cases are assigned to the other user so the original user
        # should not have them. however, the first sync should send them down (with new ownership)
        # so that they can be purged.

        # original user syncs again
        payload = generate_restore_payload(
            self.project, self.user, latest_sync_log.get_id, version=V2,
            **self.restore_options
        )
        check_payload_has_case_ids(
            self,
            username=self.user.username,
            payload_string=payload,
            case_ids=[case_id, parent_id],
        )
        # hacky
        self.assertTrue("something new" in payload)
        self.assertTrue("hi!" in payload)
        # also check that they are not sent to the phone on next sync
        next_sync_log = self.get_next_sync_log(restore_id=latest_sync_log.get_id, version=V2)
        assert_user_doesnt_have_cases(self, self.user, [case_id, parent_id],
            restore_id=next_sync_log.get_id)

        # change the parent again from the second user
        other_parent_update = CaseBlock(
            create=False,
            case_id=parent_id,
            user_id=self.other_user_id,
            owner_id=self.other_user_id,
            update={"other_greeting": "something different"}).as_xml()
        self._postFakeWithSyncToken(other_parent_update, other_sync_log.get_id)

        # original user syncs again
        latest_sync_log = SyncLog.last_for_user(self.user.user_id)
        # should be no changes
        assert_user_doesnt_have_cases(self, self.user, [case_id, parent_id], restore_id=latest_sync_log.get_id)

        # change the child again from the second user
        other_child_update = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.other_user_id,
            owner_id=self.other_user_id,
            update={"childgreeting": "hi changed!"},
        ).as_xml()
        self._postFakeWithSyncToken(other_child_update, other_sync_log.get_id)

        # original user syncs again
        latest_sync_log = SyncLog.last_for_user(self.user.user_id)
        # should be no changes
        assert_user_doesnt_have_cases(self, self.user, [case_id, parent_id], restore_id=latest_sync_log.get_id)

        # change owner of child back to orginal user from second user
        child_reassignment = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.other_user_id,
            owner_id=self.user.user_id,
        ).as_xml()
        self._postFakeWithSyncToken(child_reassignment, other_sync_log.get_id)

        # original user syncs again
        latest_sync_log = SyncLog.last_for_user(self.user.user_id)
        payload = generate_restore_payload(
            self.project, self.user, latest_sync_log.get_id, version=V2,
            **self.restore_options
        )
        # both cases should now sync
        check_payload_has_case_ids(
            self,
            payload_string=payload,
            username=self.user.username,
            case_ids=[case_id, parent_id]
        )
        # hacky
        self.assertTrue("something different" in payload)
        self.assertTrue("hi changed!" in payload)

    def testComplicatedGatesBug(self):
        # found this bug in the wild, used the real (test) forms to fix it
        # just running through this test used to fail hard, even though there
        # are no asserts
        folder_path = os.path.join("bugs", "dependent_case_conflicts")
        files = ["reg1.xml", "reg2.xml", "cf.xml", "close.xml"]
        for f in files:
            form = self._postWithSyncToken(os.path.join(folder_path, f), self.sync_log.get_id)
            self.assertFalse(hasattr(form, "problem") and form.problem)
            self.get_next_sync_log(version="2.0")

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
                    attrs={'owner_id': self.shared_group._id},
                )
            ],
            form_extras={'last_sync_token': None}
        )
        latest_sync_log = self.get_next_sync_log(restore_id=self.sync_log._id)
        self._testUpdate(latest_sync_log._id, {child_id: [index_ref], parent_id: []})

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
        latest_sync_log = self.get_next_sync_log(restore_id=self.sync_log._id)
        new_mom_ref = CommCareCaseIndex(identifier='mom', referenced_type='mom', referenced_id=new_mom_id)
        self._testUpdate(latest_sync_log._id, {
            child_id: [new_mom_ref, dad_ref], mom_id: [], dad_id: [], new_mom_id: []
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
            self.factory.create_or_update_cases([episode])
            return person, occurrence, episode

        p1, o1, e1 = create_case_graph(1)
        p2, o2, e2 = create_case_graph(2)

        # Alice and Bob sync
        alice = self.get_device()
        bob = self.get_device(user=self.other_user)
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
        self.assertEqual(sync2.case_ids, {e1.case_id, e3.case_id})

        sync3 = alice.sync()
        self.assertEqual(set(sync3.log.case_ids_on_phone), alice_cases)
        self.assertEqual(sync3.case_ids, set())


@use_sql_backend
class MultiUserSyncTestSQL(MultiUserSyncTest):
    pass


class LiveQueryMultiUserSyncTest(MultiUserSyncTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryMultiUserSyncTestSQL(LiveQueryMultiUserSyncTest):
    pass


class SteadyStateExtensionSyncTest(SyncBaseTest):
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
        cls.other_user_id = cls.other_user.user_id
        cls._create_ownership_cleanliness(cls.user_id)
        cls._create_ownership_cleanliness(cls.other_user_id)

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
        self.factory.create_or_update_case(extension)
        return host, extension

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
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
            attrs={'owner_id': self.other_user_id}
        )
        self.factory.create_or_update_case(re_assigned_extension)

        # other user should sync the host
        assert_user_has_case(self, self.other_user, host.case_id)

        # original user should sync the extension because it has changed
        sync_log_id = SyncLog.last_for_user(self.user_id)._id
        assert_user_has_case(self, self.user, extension.case_id,
                             restore_id=sync_log_id)
        # but not the host, because that didn't
        assert_user_doesnt_have_case(self, self.user, host.case_id,
                                     restore_id=sync_log_id)

        # syncing again by original user should not pull anything
        sync_again_id = SyncLog.last_for_user(self.user_id)._id
        assert_user_doesnt_have_cases(self, self.user, [extension.case_id, host.case_id],
                                     restore_id=sync_again_id)

        # reassign the extension case
        re_assigned_extension = CaseStructure(
            case_id='extension',
            attrs={'owner_id': '-'}
        )
        self.factory.create_or_update_case(re_assigned_extension)

        # make sure other_user gets it because it changed
        assert_user_has_case(self, self.other_user, extension.case_id,
                             restore_id=SyncLog.last_for_user(self.other_user_id)._id)
        # first user should also get it since it was updated
        assert_user_has_case(
            self,
            self.user,
            extension.case_id,
            restore_id=SyncLog.last_for_user(self.user_id)._id
        )

        # other user syncs again, should not get the extension
        assert_user_doesnt_have_case(self, self.other_user, extension.case_id,
                                     restore_id=SyncLog.last_for_user(self.other_user_id)._id)

        # Hooray!

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_multiple_syncs(self):
        host, extension = self._create_extension()
        assert_user_has_cases(self, self.user, [host.case_id, extension.case_id])

        sync_log = SyncLog.last_for_user(self.user_id)
        self.assertItemsEqual(sync_log.case_ids_on_phone, ['host', 'extension'])

        generate_restore_payload(
            self.project, self.user, restore_id=sync_log._id, version=V2,
            **self.restore_options
        )
        second_sync_log = SyncLog.last_for_user(self.user_id)
        self.assertItemsEqual(second_sync_log.case_ids_on_phone, ['host', 'extension'])

        generate_restore_payload(
            self.project, self.user, restore_id=second_sync_log._id, version=V2,
            **self.restore_options
        )
        third_sync_log = SyncLog.last_for_user(self.user_id)
        self.assertItemsEqual(third_sync_log.case_ids_on_phone, ['host', 'extension'])


@use_sql_backend
class SteadyStateExtensionSyncTestSQL(SteadyStateExtensionSyncTest):
    pass


class LiveQuerySteadyStateExtensionSyncTest(SteadyStateExtensionSyncTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySteadyStateExtensionSyncTestSQL(LiveQuerySteadyStateExtensionSyncTest):
    pass


class SyncTokenReprocessingTest(SyncBaseTest):
    """
    Tests sync token logic for fixing itself when it gets into a bad state.
    """

    def testUpdateNonExisting(self):
        case_id = 'non_existent'
        caseblock = CaseBlock(
            create=False,
            case_id=case_id,
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type=PARENT_TYPE,
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
            user_id=self.user_id,
            owner_id=self.user_id,
            case_type=PARENT_TYPE,
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
        ).as_xml() for case_id in [case_id1, case_id2]]

        post_case_blocks(
            initial_caseblocks,
        )

        def _get_bad_caseblocks(ids):
            return [CaseBlock(
                create=False,
                case_id=id,
                user_id=self.user_id,
                owner_id=self.user_id,
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


@use_sql_backend
class SyncTokenReprocessingTestSQL(SyncTokenReprocessingTest):
    pass


class LiveQuerySyncTokenReprocessingTest(SyncTokenReprocessingTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQuerySyncTokenReprocessingTestSQL(LiveQuerySyncTokenReprocessingTest):
    pass


class LooseSyncTokenValidationTest(SyncBaseTest):

    def test_submission_with_bad_log_toggle_enabled(self):
        domain = 'submission-domain-with-toggle'

        def _test():
            post_case_blocks(
                [CaseBlock(create=True, case_id='bad-log-toggle-enabled').as_xml()],
                form_extras={"last_sync_token": 'not-a-valid-synclog-id'},
                domain=domain,
            )

        # this is just asserting that an exception is not raised when there's no synclog
        _test()

    def test_restore_with_bad_log_toggle_enabled(self):
        domain = 'restore-domain-with-toggle'

        def _test():
            RestoreConfig(
                project=Domain(name=domain),
                restore_user=self.user,
                params=RestoreParams(
                    version=V2,
                    sync_log_id='not-a-valid-synclog-id',
                ),
                **self.restore_options
            ).get_payload()

        with self.assertRaises(RestoreException):
            _test()


@use_sql_backend
class LooseSyncTokenValidationTestSQL(LooseSyncTokenValidationTest):
    pass


class LiveQueryLooseSyncTokenValidationTest(LooseSyncTokenValidationTest):
    restore_options = {'case_sync': LIVEQUERY}


@use_sql_backend
class LiveQueryLooseSyncTokenValidationTestSQL(LiveQueryLooseSyncTokenValidationTest):
    pass


class IndexSyncTest(SyncBaseTest):

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
        self.assertEqual(sync.case_ids, {child_id, parent_id, other_parent_id})
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
