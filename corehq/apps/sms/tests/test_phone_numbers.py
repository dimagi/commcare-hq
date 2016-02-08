from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import CommConnectCase
from datetime import datetime
from django.test import TestCase


class PhoneNumberTestCase(TestCase):
    
    def setUp(self):
        pass

    def tearDown(self):
        pass

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
