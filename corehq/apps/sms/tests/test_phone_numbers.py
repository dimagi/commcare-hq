from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import CommConnectCase
from datetime import datetime, timedelta
from django.test import TestCase


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


class CaseContactPhoneNumberTestCase(TestCase):
    def get_case_verified_number(self, case):
        return CommConnectCase.wrap_as_commconnect_case(case).get_verified_number()

    def assertPhoneNumberDetails(self, case, phone_number, sms_backend_id, ivr_backend_id, _id=None, _rev=None):
        v = self.get_case_verified_number(case)
        self.assertEqual(v.domain, case.domain)
        self.assertEqual(v.owner_doc_type, case.doc_type)
        self.assertEqual(v.owner_id, case._id)
        self.assertEqual(v.phone_number, phone_number)
        self.assertEqual(v.backend_id, sms_backend_id)
        self.assertEqual(v.ivr_backend_id, ivr_backend_id)
        self.assertEqual(v.verified, True)
        self.assertEqual(v.contact_last_modified, case.server_modified_on)

        if _id:
            self.assertEqual(v._id, _id)

        if _rev:
            self.assertTrue(v._rev.startswith(_rev + '-'))

    def test_case_phone_number_updates(self):
        case = CommCareCase(
            domain='case-phone-number-test',
            name='TEST1'
        )
        case.save()
        self.assertIsNone(self.get_case_verified_number(case))

        case.set_case_property('contact_phone_number', '99987658765')
        case.save()
        self.assertIsNone(self.get_case_verified_number(case))

        case.set_case_property('contact_phone_number_is_verified', '1')
        case.save()
        self.assertPhoneNumberDetails(case, '99987658765', None, None, _rev='1')
        _id = self.get_case_verified_number(case)._id

        case.set_case_property('contact_phone_number', '99987698769')
        case.save()
        self.assertPhoneNumberDetails(case, '99987698769', None, None, _id=_id, _rev='2')

        case.set_case_property('contact_backend_id', 'sms-backend')
        case.save()
        self.assertPhoneNumberDetails(case, '99987698769', 'sms-backend', None, _id=_id, _rev='3')

        case.set_case_property('contact_ivr_backend_id', 'ivr-backend')
        case.save()
        self.assertPhoneNumberDetails(case, '99987698769', 'sms-backend', 'ivr-backend', _id=_id, _rev='4')

        # If nothing changes, the phone entry should not be saved
        case.save()
        self.assertTrue(self.get_case_verified_number(case)._rev.startswith('4-'))

        # If phone entry is ahead of the case in terms of contact_last_modified, no update should happen
        v = self.get_case_verified_number(case)
        v.contact_last_modified += timedelta(days=1)
        v.save()
        self.assertTrue(v._rev.startswith('5-'))

        case.set_case_property('contact_phone_number', '99912341234')
        case.save()
        self.assertTrue(self.get_case_verified_number(case)._rev.startswith('5-'))

        self.get_case_verified_number(case).delete()
        case.delete()

    def test_close_case(self):
        case = CommCareCase(
            domain='case-phone-number-test',
            name='TEST1'
        )
        case.set_case_property('contact_phone_number', '99987658765')
        case.set_case_property('contact_phone_number_is_verified', '1')
        case.save()
        self.assertIsNotNone(self.get_case_verified_number(case))

        case.closed = True
        case.save()
        self.assertIsNone(self.get_case_verified_number(case))
        case.delete()

    def test_case_soft_delete(self):
        case = CommCareCase(
            domain='case-phone-number-test',
            name='TEST1'
        )
        case.set_case_property('contact_phone_number', '99987658765')
        case.set_case_property('contact_phone_number_is_verified', '1')
        case.save()
        self.assertIsNotNone(self.get_case_verified_number(case))

        case.doc_type += '-Deleted'
        case.save()
        self.assertIsNone(self.get_case_verified_number(case))
        case.delete()

    def test_case_zero_phone_number(self):
        case = CommCareCase(
            domain='case-phone-number-test',
            name='TEST1'
        )
        case.set_case_property('contact_phone_number', '99987658765')
        case.set_case_property('contact_phone_number_is_verified', '1')
        case.save()
        self.assertIsNotNone(self.get_case_verified_number(case))

        case.set_case_property('contact_phone_number', '0')
        case.save()
        self.assertIsNone(self.get_case_verified_number(case))
        case.delete()

    def test_invalid_phone_format(self):
        case = CommCareCase(
            domain='case-phone-number-test',
            name='TEST1'
        )
        case.set_case_property('contact_phone_number', '99987658765')
        case.set_case_property('contact_phone_number_is_verified', '1')
        case.save()
        self.assertIsNotNone(self.get_case_verified_number(case))

        case.set_case_property('contact_phone_number', 'xyz')
        case.save()
        self.assertIsNone(self.get_case_verified_number(case))
        case.delete()

    def test_phone_number_already_in_use(self):
        case1 = CommCareCase(
            domain='case-phone-number-test',
            name='TEST1'
        )
        case1.set_case_property('contact_phone_number', '99987658765')
        case1.set_case_property('contact_phone_number_is_verified', '1')
        case1.save()

        case2 = CommCareCase(
            domain='case-phone-number-test',
            name='TEST2'
        )
        case2.set_case_property('contact_phone_number', '99987698769')
        case2.set_case_property('contact_phone_number_is_verified', '1')
        case2.save()

        self.assertIsNotNone(self.get_case_verified_number(case1))
        self.assertIsNotNone(self.get_case_verified_number(case2))

        case2.set_case_property('contact_phone_number', '99987658765')
        case2.save()
        self.assertIsNotNone(self.get_case_verified_number(case1))
        self.assertIsNone(self.get_case_verified_number(case2))

        case2.delete()
        self.get_case_verified_number(case1).delete()
        case1.delete()

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
