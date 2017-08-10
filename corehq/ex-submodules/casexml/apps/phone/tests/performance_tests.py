from unittest import skip
from casexml.apps.case.mock import CaseBlock, CaseStructure
from casexml.apps.phone.tests.test_sync_mode import SyncBaseTest, PARENT_TYPE
from casexml.apps.phone.tests.utils import (
    synclog_from_restore_payload,
    generate_restore_payload,
    create_restore_user,
)
from casexml.apps.case.tests.util import assert_user_has_cases
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


class SyncPerformanceTest(SyncBaseTest):
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

    def setUp(self):
        super(SyncPerformanceTest, self).setUp()
        # the other user is an "owner" of the original users cases as well,
        # for convenience
        self.project = Domain(name='sync-performance-tests')
        self.project.save()
        self.factory.domain = self.project.name
        self.other_user = create_restore_user(
            domain=self.project.name,
            username=OTHER_USERNAME,
        )

        self.referral_user = create_restore_user(
            domain=self.project.name,
            username=REFERRAL_USERNAME,
        )

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
        self.other_sync_log = synclog_from_restore_payload(generate_restore_payload(
            self.project, self.other_user
        ))
        self.referral_sync_log = synclog_from_restore_payload(generate_restore_payload(
            self.project, self.referral_user
        ))

        self.assertTrue(self.shared_group._id in self.other_sync_log.owner_ids_on_phone)
        self.assertTrue(self.other_user.user_id in self.other_sync_log.owner_ids_on_phone)

        self.sync_log = synclog_from_restore_payload(generate_restore_payload(
            self.project, self.user
        ))
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
        assert_user_has_cases(self, self.referral_user, all_cases, restore_id=self.referral_sync_log.get_id)

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
        assert_user_has_cases(self, self.referral_user, all_cases, restore_id=self.referral_sync_log.get_id)
