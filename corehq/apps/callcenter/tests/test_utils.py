from datetime import datetime, timedelta
import pytz
from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.callcenter.utils import sync_call_center_user_case, is_midnight_for_domain, get_call_center_cases, \
    DomainLite
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.users.models import CommCareUser
from django.test import TestCase, SimpleTestCase
from dimagi.utils.couch.undo import DELETED_SUFFIX

TEST_DOMAIN = 'cc_util_test'
CASE_TYPE = 'cc_flw'


class CallCenterUtilsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain(TEST_DOMAIN)
        user = CommCareUser.create(TEST_DOMAIN, 'user1', '***')
        cls.user_id = user.user_id

        cls.domain.call_center_config.enabled = True
        cls.domain.call_center_config.case_owner_id = user.user_id
        cls.domain.call_center_config.case_type = CASE_TYPE
        cls.domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

    def setUp(self):
        self.user = CommCareUser.get(self.user_id)

    def tearDown(self):
        delete_all_cases()

    def test_sync(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, self.user.username)
        self.assertEquals(case.username, self.user.raw_username)
        self.assertIsNotNone(case.language)
        self.assertIsNotNone(case.phone_number)

    def test_sync_full_name(self):
        name = 'Ricky Bowwood'
        self.user.set_full_name(name)
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, name)

    def test_sync_inactive(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)

        self.user.is_active = False
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertTrue(case.closed)

    def test_sync_retired(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)

        self.user.base_doc += DELETED_SUFFIX
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertTrue(case.closed)

    def test_sync_update_update(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, self.user.username)

        name = 'Ricky Bowwood'
        self.user.set_full_name(name)
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
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
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.blank_val, '')
        self.assertEquals(case.ok, 'good')

    def test_get_call_center_cases_for_user(self):
        factory = CaseFactory(domain=TEST_DOMAIN, case_defaults={
            'user_id': self.user_id,
            'owner_id': self.user_id,
            'case_type': CASE_TYPE,
            'update': {'hq_user_id': self.user_id}
        })
        c1, c2, c3 = factory.create_or_update_cases([
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True, 'owner_id': 'another_user'}),
        ])
        cases = get_call_center_cases(TEST_DOMAIN, CASE_TYPE, self.user)
        self.assertEqual(len(cases), 2)
        case_ids = {case.case_id for case in cases}
        user_ids = {case.hq_user_id for case in cases}
        self.assertEqual(case_ids, set([c1.case_id, c2.case_id]))
        self.assertEqual(user_ids, set([self.user_id]))

    def test_get_call_center_cases_all(self):
        factory = CaseFactory(domain=TEST_DOMAIN, case_defaults={
            'user_id': self.user_id,
            'owner_id': self.user_id,
            'case_type': CASE_TYPE,
            'update': {'hq_user_id': self.user_id}
        })
        factory.create_or_update_cases([
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True, 'owner_id': 'another_user'}),
        ])
        cases = get_call_center_cases(TEST_DOMAIN, CASE_TYPE)
        self.assertEqual(len(cases), 3)


class DomainTimezoneTests(SimpleTestCase):
    def test_midnight_for_domain(self):
        midnight_past = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_future = midnight_past + timedelta(days=1)
        timezones = [
            ('Asia/Kolkata', 5.5),
            ('UTC', 0),
            ('Africa/Lagos', 1),
            ('America/New_York', -5),
            ('US/Eastern', -5),
            ('Europe/London', 0),
            ('Asia/Baghdad', 3),
            ('America/Port-au-Prince', -5),
            ('Africa/Porto-Novo', 1),
            ('Africa/Nairobi', 3),
        ]
        for tz, offset in timezones:
            # account for DST
            offset += datetime.now(pytz.timezone(tz)).dst().total_seconds() / 3600

            dom = DomainLite(name='', default_timezone=tz, cc_case_type='')
            self.assertEqual(dom.midnights[0], midnight_past - timedelta(hours=offset), tz)
            self.assertEqual(dom.midnights[1], midnight_future - timedelta(hours=offset), tz)

    def test_is_midnight_for_domain(self):
        midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        midnights = [
            (midnight, True),
            (midnight + timedelta(minutes=10), True),
            (midnight + timedelta(minutes=20), False),
            (midnight - timedelta(minutes=1), False),
        ]
        for midnight_candidate, expected in midnights:
            is_midnight = is_midnight_for_domain(midnight, current_time=midnight_candidate)
            self.assertEqual(is_midnight, expected)
