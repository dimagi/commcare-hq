from casexml.apps.case.mock import CaseBlock
from casexml.apps.phone.caselogic import filter_cases_modified_elsewhere_since_sync, get_related_cases
from casexml.apps.phone.tests.test_sync_mode import SyncBaseTest, PARENT_TYPE
from casexml.apps.phone.tests.utils import synclog_from_restore_payload
from casexml.apps.case.tests.util import assert_user_has_cases
from casexml.apps.phone.models import User
from casexml.apps.phone.restore import generate_restore_payload, RestoreConfig, get_case_payload, \
    get_case_payload_batched
from dimagi.utils.decorators.profile import line_profile
from casexml.apps.case.xml import V2
from datetime import datetime

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

    def setUp(self):
        super(SyncPerformanceTest, self).setUp()
        # the other user is an "owner" of the original users cases as well,
        # for convenience
        self.other_user = User(user_id=OTHER_USER_ID, username=OTHER_USERNAME,
                               password="changeme", date_joined=datetime(2011, 6, 9),
                               additional_owner_ids=[SHARED_ID])

        self.referral_user = User(user_id=REFERRAL_USER_ID, username=REFERRAL_USERNAME,
                               password="changeme", date_joined=datetime(2011, 6, 9),
                               additional_owner_ids=[REFERRED_TO_GROUP])

        # this creates the initial blank sync token in the database
        self.other_sync_log = synclog_from_restore_payload(generate_restore_payload(self.other_user))
        self.referral_sync_log = synclog_from_restore_payload(generate_restore_payload(self.referral_user))

        self.assertTrue(SHARED_ID in self.other_sync_log.owner_ids_on_phone)
        self.assertTrue(OTHER_USER_ID in self.other_sync_log.owner_ids_on_phone)

        self.user.additional_owner_ids = [SHARED_ID]
        self.sync_log = synclog_from_restore_payload(generate_restore_payload(self.user))
        self.assertTrue(SHARED_ID in self.sync_log.owner_ids_on_phone)
        self.assertTrue(USER_ID in self.sync_log.owner_ids_on_phone)

    @line_profile([
        RestoreConfig.get_payload,
        get_case_payload,
        get_case_payload_batched,
        get_related_cases,
        filter_cases_modified_elsewhere_since_sync
    ])
    def test_profile_filter_cases_modified_elsewhere_since_sync(self):
        total_cases = 100
        proportion_modified = 0

        modified = total_cases * proportion_modified
        id_list = ['case_id_{}'.format(i) for i in range(total_cases)]
        self._createCaseStubs(id_list, user_id=USER_ID, owner_id=SHARED_ID)

        for case_id in id_list[:modified]:
            caseblock = CaseBlock(
                case_id=case_id,
                user_id=OTHER_USER_ID,
                version=V2,
                update={'favorite_color': 'blue'}
            ).as_xml()
            self._postFakeWithSyncToken(caseblock, self.other_sync_log.get_id)

        assert_user_has_cases(self, self.user, id_list[:modified], restore_id=self.sync_log.get_id)

    @line_profile([
        RestoreConfig.get_payload,
        get_case_payload,
        get_case_payload_batched,
        get_related_cases,
        filter_cases_modified_elsewhere_since_sync
    ])
    def test_profile_get_related_cases(self):
        total_parent_cases = 50

        id_list = ['case_id_{}'.format(i) for i in range(total_parent_cases)]
        self._createCaseStubs(id_list, user_id=USER_ID, owner_id=SHARED_ID)

        new_case_ids = []
        for i, parent_case_id in enumerate(id_list):
            case_id = 'case_id_referral_{}'.format(i)
            new_case_ids.append(case_id)
            caseblock = CaseBlock(
                create=True,
                case_id=case_id,
                user_id=USER_ID,
                owner_id=REFERRED_TO_GROUP,
                case_type=REFERRAL_TYPE,
                version=V2,
                index={'parent': (PARENT_TYPE, parent_case_id)}
            ).as_xml()
            self._postFakeWithSyncToken(caseblock, self.sync_log.get_id)

        all_cases = id_list + new_case_ids
        assert_user_has_cases(self, self.referral_user, all_cases, restore_id=self.referral_sync_log.get_id)

    @line_profile([
        RestoreConfig.get_payload,
        get_case_payload,
        get_case_payload_batched,
        get_related_cases,
        filter_cases_modified_elsewhere_since_sync
    ])
    def test_profile_get_related_cases_grandparent(self):
        total_parent_cases = 30

        parent_cases = ['case_id_{}'.format(i) for i in range(total_parent_cases)]
        self._createCaseStubs(parent_cases, user_id=USER_ID, owner_id=SHARED_ID)

        child_cases = []
        for i, parent_case_id in enumerate(parent_cases):
            case_id = 'case_id_child_{}'.format(i)
            child_cases.append(case_id)
            caseblock = CaseBlock(
                create=True,
                case_id=case_id,
                user_id=USER_ID,
                owner_id=SHARED_ID,
                case_type='child',
                version=V2,
                index={'parent': (PARENT_TYPE, parent_case_id)}
            ).as_xml()
            self._postFakeWithSyncToken(caseblock, self.sync_log.get_id)
            print("created child case", case_id)

        referreal_cases = []
        for i, child_case_id in enumerate(child_cases):
            case_id = 'case_id_referral_{}'.format(i)
            referreal_cases.append(case_id)
            caseblock = CaseBlock(
                create=True,
                case_id=case_id,
                user_id=USER_ID,
                owner_id=REFERRED_TO_GROUP,
                case_type=REFERRAL_TYPE,
                version=V2,
                index={'parent': ('child', child_case_id)}
            ).as_xml()
            self._postFakeWithSyncToken(caseblock, self.sync_log.get_id)
            print("created referral case", case_id)

        all_cases = parent_cases + child_cases + referreal_cases
        assert_user_has_cases(self, self.referral_user, all_cases, restore_id=self.referral_sync_log.get_id)
