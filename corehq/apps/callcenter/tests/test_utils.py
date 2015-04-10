from corehq.apps.callcenter.utils import sync_call_center_user_case
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.users.models import CommCareUser
from django.test import TestCase
from dimagi.utils.couch.undo import DELETED_SUFFIX

TEST_DOMAIN = 'cc_util_test'


class CallCenterUtilsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain(TEST_DOMAIN)
        user = CommCareUser.create(TEST_DOMAIN, 'user1', '***')
        cls.user_id = user.user_id

        cls.domain.call_center_config.enabled = True
        cls.domain.call_center_config.case_owner_id = user.user_id
        cls.domain.call_center_config.case_type = 'cc_flw'
        cls.domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

    def setUp(self):
        self.user = CommCareUser.get(self.user_id)

    def tearDown(self):
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        case.delete()

    def test_sync(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, self.user.username)
        self.assertEquals(case.username, self.user.raw_username)
        self.assertIsNotNone(case.language)
        self.assertIsNotNone(case.phone_number)

    def test_sync_full_name(self):
        name = 'Ricky Bowwood'
        self.user.set_full_name(name)
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, name)

    def test_sync_inactive(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertIsNotNone(case)

        self.user.is_active = False
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertTrue(case.closed)

    def test_sync_retired(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertIsNotNone(case)

        self.user.base_doc += DELETED_SUFFIX
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertTrue(case.closed)

    def test_sync_update_update(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, self.user.username)

        name = 'Ricky Bowwood'
        self.user.set_full_name(name)
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertEquals(case.name, name)

    def test_sync_custom_user_data(self):
        self.user.user_data = {
            '': 'blank_key',
            'blank_val': '',
            'ok': 'good',
            'name with spaces': 'ok',
            '8starts_with_a_number': '0',
            'xml_starts_with_xml': '0',
            '._starts_with_punctuation': '0',
        }
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, include_docs=True)
        self.assertIsNotNone(case)
        self.assertEquals(case.blank_val, '')
        self.assertEquals(case.ok, 'good')
