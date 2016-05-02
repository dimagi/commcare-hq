from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.models import CommCareCase
from contextlib import contextmanager
from corehq.apps.hqcase.utils import update_case
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.users.tasks import tag_cases_as_deleted_and_remove_indices
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.utils.general import should_use_sql_backend
from datetime import datetime, timedelta
from django.test import TestCase
from corehq.form_processor.tests.utils import run_with_all_backends


class PhoneNumberLookupTestCase(TestCase):

    def assertNoMatch(self, phone_search, suffix_search, owner_id_search):
        self.assertIsNone(VerifiedNumber.by_phone(phone_search))
        self.assertIsNone(VerifiedNumber.by_suffix(suffix_search))
        self.assertEqual(VerifiedNumber.by_owner_id(owner_id_search), [])

    def assertMatch(self, match, phone_search, suffix_search, owner_id_search):
        lookedup = VerifiedNumber.by_phone(phone_search)
        self.assertEqual(match._id, lookedup._id)
        self.assertEqual(match._rev, lookedup._rev)

        lookedup = VerifiedNumber.by_suffix(suffix_search)
        self.assertEqual(match._id, lookedup._id)
        self.assertEqual(match._rev, lookedup._rev)

        [lookedup] = VerifiedNumber.by_owner_id(owner_id_search)
        self.assertEqual(match._id, lookedup._id)
        self.assertEqual(match._rev, lookedup._rev)

    def _test_cache_clear(self, refresh_each_time=True):
        """
        A test to make sure that the cache clearing is working as expected.
        This test gets run twice using different values for refresh_each_time.
        This makes sure that the mechanism used for clearing the cache works
        whether you're updating a document you just saved or getting a document
        fresh from the database and updating it.
        """
        created = VerifiedNumber(
            domain='phone-number-test',
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-id1',
            phone_number='99912341234',
            backend_id=None,
            ivr_backend_id=None,
            verified=True,
            contact_last_modified=datetime.utcnow()
        )
        created.save()
        self.assertTrue(created._rev.startswith('1-'))
        self.assertNoMatch('99952345234', '52345234', 'fake-owner-id2')
        self.assertMatch(created, '99912341234', '12341234', 'fake-owner-id1')

        # Update Phone Number
        if refresh_each_time:
            created = VerifiedNumber.get(created._id)
        created.phone_number = '99952345234'
        created.save()
        self.assertTrue(created._rev.startswith('2-'))
        self.assertNoMatch('99912341234', '12341234', 'fake-owner-id2')
        self.assertMatch(created, '99952345234', '52345234', 'fake-owner-id1')

        # Update Owner Id
        if refresh_each_time:
            created = VerifiedNumber.get(created._id)
        created.owner_id = 'fake-owner-id2'
        created.save()
        self.assertTrue(created._rev.startswith('3-'))
        self.assertNoMatch('99912341234', '12341234', 'fake-owner-id1')
        self.assertMatch(created, '99952345234', '52345234', 'fake-owner-id2')

        created.delete()
        self.assertNoMatch('99952345234', '52345234', 'fake-owner-id2')

    def test_cache_clear_with_refresh(self):
        self._test_cache_clear(refresh_each_time=True)

    def test_cache_clear_without_refresh(self):
        self._test_cache_clear(refresh_each_time=False)


@contextmanager
def create_test_case(domain, case_type, case_name):
    case = CaseFactory(domain).create_case(
        case_type=case_type,
        case_name=case_name
    )
    try:
        yield case
    finally:
        if should_use_sql_backend(domain):
            CaseAccessorSQL.hard_delete_cases(domain, [case.case_id])
        else:
            case.delete()


class CaseContactPhoneNumberTestCase(TestCase):

    def setUp(self):
        self.domain = 'case-phone-number-test'

    def tearDown(self):
        for v in VerifiedNumber.by_domain(self.domain):
            v.delete()

    def set_case_property(self, case, property_name, value):
        update_case(self.domain, case.case_id, case_properties={property_name: value})
        return CaseAccessors(self.domain).get_case(case.case_id)

    def get_case_verified_number(self, case):
        return case.get_verified_number()

    def assertPhoneNumberDetails(self, case, phone_number, sms_backend_id, ivr_backend_id, _id=None, _rev=None):
        v = self.get_case_verified_number(case)
        self.assertEqual(v.domain, case.domain)
        self.assertEqual(v.owner_doc_type, case.doc_type)
        self.assertEqual(v.owner_id, case.case_id)
        self.assertEqual(v.phone_number, phone_number)
        self.assertEqual(v.backend_id, sms_backend_id)
        self.assertEqual(v.ivr_backend_id, ivr_backend_id)
        self.assertEqual(v.verified, True)
        self.assertEqual(v.contact_last_modified, case.server_modified_on)

        if _id:
            self.assertEqual(v._id, _id)

        if _rev:
            self.assertTrue(v._rev.startswith(_rev + '-'))

    @run_with_all_backends
    def test_case_phone_number_updates(self):
        with create_test_case(self.domain, 'participant', 'test1') as case:
            self.assertIsNone(self.get_case_verified_number(case))

            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            self.assertIsNone(self.get_case_verified_number(case))

            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertPhoneNumberDetails(case, '99987658765', None, None, _rev='1')
            _id = self.get_case_verified_number(case)._id

            case = self.set_case_property(case, 'contact_phone_number', '99987698769')
            self.assertPhoneNumberDetails(case, '99987698769', None, None, _id=_id, _rev='2')

            case = self.set_case_property(case, 'contact_backend_id', 'sms-backend')
            self.assertPhoneNumberDetails(case, '99987698769', 'sms-backend', None, _id=_id, _rev='3')

            case = self.set_case_property(case, 'contact_ivr_backend_id', 'ivr-backend')
            self.assertPhoneNumberDetails(case, '99987698769', 'sms-backend', 'ivr-backend', _id=_id, _rev='4')

            # If nothing changes, the phone entry should not be saved
            case = self.set_case_property(case, 'abc', 'def')
            self.assertTrue(self.get_case_verified_number(case)._rev.startswith('4-'))

            # If phone entry is ahead of the case in terms of contact_last_modified, no update should happen
            v = self.get_case_verified_number(case)
            v.contact_last_modified += timedelta(days=1)
            v.save()
            self.assertTrue(v._rev.startswith('5-'))

            case = self.set_case_property(case, 'contact_phone_number', '99912341234')
            self.assertTrue(self.get_case_verified_number(case)._rev.startswith('5-'))

    @run_with_all_backends
    def test_close_case(self):
        with create_test_case(self.domain, 'participant', 'test1') as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_verified_number(case))

            update_case(self.domain, case.case_id, close=True)
            self.assertIsNone(self.get_case_verified_number(case))

    @run_with_all_backends
    def test_case_soft_delete(self):
        with create_test_case(self.domain, 'participant', 'test1') as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_verified_number(case))

            tag_cases_as_deleted_and_remove_indices(self.domain, [case.case_id], '123', datetime.utcnow())
            self.assertIsNone(self.get_case_verified_number(case))

    @run_with_all_backends
    def test_case_zero_phone_number(self):
        with create_test_case(self.domain, 'participant', 'test1') as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_verified_number(case))

            case = self.set_case_property(case, 'contact_phone_number', '0')
            self.assertIsNone(self.get_case_verified_number(case))

    @run_with_all_backends
    def test_invalid_phone_format(self):
        with create_test_case(self.domain, 'participant', 'test1') as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_verified_number(case))

            case = self.set_case_property(case, 'contact_phone_number', 'xyz')
            self.assertIsNone(self.get_case_verified_number(case))

    @run_with_all_backends
    def test_phone_number_already_in_use(self):
        with create_test_case(self.domain, 'participant', 'test1') as case1, \
                create_test_case(self.domain, 'participant', 'test2') as case2:
            case1 = self.set_case_property(case1, 'contact_phone_number', '99987658765')
            case1 = self.set_case_property(case1, 'contact_phone_number_is_verified', '1')

            case2 = self.set_case_property(case2, 'contact_phone_number', '99987698769')
            case2 = self.set_case_property(case2, 'contact_phone_number_is_verified', '1')

            self.assertIsNotNone(self.get_case_verified_number(case1))
            self.assertIsNotNone(self.get_case_verified_number(case2))

            case2 = self.set_case_property(case2, 'contact_phone_number', '99987658765')

            self.assertIsNotNone(self.get_case_verified_number(case1))
            self.assertIsNone(self.get_case_verified_number(case2))

    def test_filter_pending(self):
        v1 = VerifiedNumber(verified=True)
        v1.save()

        v2 = VerifiedNumber(verified=False)
        v2.save()

        self.assertIsNone(VerifiedNumber._filter_pending(None, include_pending=True))
        self.assertIsNone(VerifiedNumber._filter_pending(None, include_pending=False))

        self.assertEqual(v1, VerifiedNumber._filter_pending(v1, include_pending=False))
        self.assertIsNone(VerifiedNumber._filter_pending(v2, include_pending=False))

        self.assertEqual(v1, VerifiedNumber._filter_pending(v1, include_pending=True))
        self.assertEqual(v2, VerifiedNumber._filter_pending(v2, include_pending=True))

        v1.delete()
        v2.delete()
