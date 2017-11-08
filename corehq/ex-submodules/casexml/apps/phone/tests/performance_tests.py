from __future__ import absolute_import
from unittest import skip
from casexml.apps.case.mock import CaseBlock, CaseStructure
from casexml.apps.phone.tests.test_sync_mode import (
    BaseSyncTest, DeprecatedBaseSyncTest, PARENT_TYPE
)
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.case.xml import V1
from corehq.apps.groups.models import Group
from casexml.apps.phone.restore import RestoreConfig
from dimagi.utils.decorators.profile import line_profile
from corehq.apps.domain.models import Domain

USER_ID = "main_user"
USERNAME = "syncguy"
OTHER_USER_ID = "someone_else"
OTHER_USERNAME = "ferrel"
SHARED_ID = "our_group"

REFERRAL_USERNAME = 'referral_user'
REFERRAL_USER_ID = 'referral_user_id'
REFERRED_TO_GROUP = 'other_group'
REFERRAL_TYPE = 'referral'


class SyncPerformanceTest(DeprecatedBaseSyncTest):
    """
    Tests the interaction of two users in sync mode doing various things
    """

    def _createCaseStubs(self, id_list, **kwargs):
        # TODO remove this when these tests use MockDevice
        case_attrs = {'create': True}
        case_attrs.update(kwargs)
        return self.factory.create_or_update_cases(
            [CaseStructure(case_id=case_id, attrs=case_attrs) for case_id in id_list],
        )

    def _postFakeWithSyncToken(self, caseblocks, token_id):
        # TODO remove this when these tests use MockDevice
        if not isinstance(caseblocks, list):
            # can't use list(caseblocks) since that returns children of the node
            # http://lxml.de/tutorial.html#elements-are-lists
            caseblocks = [caseblocks]
        return self.factory.post_case_blocks(caseblocks, form_extras={"last_sync_token": token_id})

    @classmethod
    def setUpClass(cls):
        # purposely skip BaseSyncTest and DeprecatedBaseSyncTest setUpClass
        super(BaseSyncTest, cls).setUpClass()
        cls.project = Domain(name='sync-performance-tests')
        cls.project.save()
        cls.user = create_restore_user(
            cls.project.name,
            USERNAME,
        )
        cls.other_user = create_restore_user(
            domain=cls.project.name,
            username=OTHER_USERNAME,
        )
        cls.referral_user = create_restore_user(
            domain=cls.project.name,
            username=REFERRAL_USERNAME,
        )

    def setUp(self):
        super(SyncPerformanceTest, self).setUp()
        # the other user is an "owner" of the original users cases as well,
        # for convenience
        self.factory.domain = self.project.name
        self.referral_device = self.get_device(user=self.referral_user)
        self.referral_device.sync(version=V1)

        self.shared_group = Group(
            domain=self.project.name,
            name='shared_group',
            case_sharing=True,
            users=[self.other_user.user_id, self.user.user_id]
        )
        self.shared_group.save()

        self.referral_group = Group(
            domain=self.project.name,
            name='referral_group',
            case_sharing=True,
            users=[self.referral_user.user_id]
        )
        self.referral_group.save()

        # this creates the initial blank sync token in the database
        other_device = self.get_device(user=self.other_user)
        other_sync_log = other_device.sync(version=V1).log

        self.assertTrue(self.shared_group._id in other_sync_log.owner_ids_on_phone)
        self.assertTrue(self.other_user.user_id in other_sync_log.owner_ids_on_phone)

        device = self.get_device(user=self.user)
        self.sync_log = device.sync(version=V1).log
        self.assertTrue(self.shared_group._id in self.sync_log.owner_ids_on_phone)
        self.assertTrue(self.user.user_id in self.sync_log.owner_ids_on_phone)

    @skip('Comment out to profile')
    @line_profile([
        RestoreConfig.get_payload,
    ])
    def test_profile_get_related_cases(self):
        total_parent_cases = 50

        id_list = ['case_id_{}'.format(i) for i in range(total_parent_cases)]
        self._createCaseStubs(
            id_list,
            user_id=self.user.user_id,
            owner_id=self.shared_group._id
        )

        new_case_ids = []
        caseblocks = []
        for i, parent_case_id in enumerate(id_list):
            case_id = 'case_id_referral_{}'.format(i)
            new_case_ids.append(case_id)
            caseblocks.append(CaseBlock(
                create=True,
                case_id=case_id,
                user_id=self.user.user_id,
                owner_id=self.referral_group._id,
                case_type=REFERRAL_TYPE,
                index={'parent': (PARENT_TYPE, parent_case_id)}
            ).as_xml())
        self._postFakeWithSyncToken(caseblocks, self.sync_log.get_id)

        all_cases = id_list + new_case_ids
        sync = self.referral_device.sync()
        self.assertEqual(set(all_cases), set(sync.cases))

    @skip('Comment out to profile')
    @line_profile([
        RestoreConfig.get_payload,
    ])
    def test_profile_get_related_cases_grandparent(self):
        total_parent_cases = 5

        parent_cases = ['case_id_{}'.format(i) for i in range(total_parent_cases)]
        self._createCaseStubs(
            parent_cases,
            user_id=self.user.user_id,
            owner_id=self.shared_group._id
        )

        child_cases = []
        caseblocks = []
        for i, parent_case_id in enumerate(parent_cases):
            case_id = 'case_id_child_{}'.format(i)
            child_cases.append(case_id)
            caseblocks.append(CaseBlock(
                create=True,
                case_id=case_id,
                user_id=self.user.user_id,
                owner_id=self.shared_group._id,
                case_type='child',
                index={'parent': (PARENT_TYPE, parent_case_id)}
            ).as_xml())
        self._postFakeWithSyncToken(caseblocks, self.sync_log.get_id)

        referreal_cases = []
        caseblocks = []
        for i, child_case_id in enumerate(child_cases):
            case_id = 'case_id_referral_{}'.format(i)
            referreal_cases.append(case_id)
            caseblocks.append(CaseBlock(
                create=True,
                case_id=case_id,
                user_id=self.user.user_id,
                owner_id=self.referral_group._id,
                case_type=REFERRAL_TYPE,
                index={'parent': ('child', child_case_id)}
            ).as_xml())
        self._postFakeWithSyncToken(caseblocks, self.sync_log.get_id)

        all_cases = parent_cases + child_cases + referreal_cases
        sync = self.referral_device.sync()
        self.assertEqual(set(all_cases), set(sync.cases))
