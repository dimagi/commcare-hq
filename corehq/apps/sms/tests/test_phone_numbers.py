from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import update_case
from corehq.apps.sms.models import (SQLMobileBackend, SQLMobileBackendMapping,
    PhoneNumber)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.tasks import tag_cases_as_deleted_and_remove_indices
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from datetime import datetime, timedelta
from django.test import TestCase
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import is_commcarecase
from corehq.util.test_utils import create_test_case


class PhoneNumberCacheClearTestCase(TestCase):

    def assertNoMatch(self, phone_search, suffix_search, owner_id_search):
        self.assertIsNone(PhoneNumber.by_phone(phone_search))
        self.assertIsNone(PhoneNumber.by_suffix(suffix_search))
        self.assertEqual(PhoneNumber.by_owner_id(owner_id_search), [])

    def assertPhoneNumbersEqual(phone1, phone2):
        for field in phone1._meta.fields:
            self.assertEqual(getattr(phone1, field), getattr(phone2, field))

    def assertMatch(self, match, phone_search, suffix_search, owner_id_search):
        lookedup = PhoneNumber.by_phone(phone_search)
        self.assertPhoneNumbersEqual(match, lookedup)

        lookedup = PhoneNumber.by_suffix(suffix_search)
        self.assertPhoneNumbersEqual(match, lookedup)

        [lookedup] = PhoneNumber.by_owner_id(owner_id_search)
        self.assertPhoneNumbersEqual(match, lookedup)

    def _test_cache_clear(self, refresh_each_time=True):
        """
        A test to make sure that the cache clearing is working as expected.
        This test gets run twice using different values for refresh_each_time.
        This makes sure that the mechanism used for clearing the cache works
        whether you're updating a document you just saved or getting a document
        fresh from the database and updating it.
        """
        created = PhoneNumber(
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
        self.assertNoMatch('99952345234', '52345234', 'fake-owner-id2')
        self.assertMatch(created, '99912341234', '12341234', 'fake-owner-id1')

        # Update Phone Number
        if refresh_each_time:
            created = PhoneNumber.objects.get(pk=created.pk)
        created.phone_number = '99952345234'
        created.save()
        self.assertNoMatch('99912341234', '12341234', 'fake-owner-id2')
        self.assertMatch(created, '99952345234', '52345234', 'fake-owner-id1')

        # Update Owner Id
        if refresh_each_time:
            created = PhoneNumber.objects.get(pk=created.pk)
        created.owner_id = 'fake-owner-id2'
        created.save()
        self.assertNoMatch('99912341234', '12341234', 'fake-owner-id1')
        self.assertMatch(created, '99952345234', '52345234', 'fake-owner-id2')

        created.delete()
        self.assertNoMatch('99952345234', '52345234', 'fake-owner-id2')

    def test_cache_clear_with_refresh(self):
        self._test_cache_clear(refresh_each_time=True)

    def test_cache_clear_without_refresh(self):
        self._test_cache_clear(refresh_each_time=False)


class CaseContactPhoneNumberTestCase(TestCase):

    def setUp(self):
        self.domain = 'case-phone-number-test'

    def tearDown(self):
        for v in PhoneNumber.by_domain(self.domain):
            # Clear cache and delete
            v.delete()

    def set_case_property(self, case, property_name, value):
        update_case(self.domain, case.case_id, case_properties={property_name: value})
        return CaseAccessors(self.domain).get_case(case.case_id)

    def get_case_verified_number(self, case):
        return case.get_verified_number()

    def assertPhoneNumberDetails(self, case, phone_number, sms_backend_id, ivr_backend_id, pk=None):
        v = self.get_case_verified_number(case)
        self.assertEqual(v.domain, case.domain)
        self.assertEqual(v.owner_doc_type, case.doc_type)
        self.assertEqual(v.owner_id, case.case_id)
        self.assertEqual(v.phone_number, phone_number)
        self.assertEqual(v.backend_id, sms_backend_id)
        self.assertEqual(v.ivr_backend_id, ivr_backend_id)
        self.assertEqual(v.verified, True)
        self.assertEqual(v.contact_last_modified, case.server_modified_on)

        if pk:
            self.assertEqual(v.pk, pk)

    @run_with_all_backends
    def test_case_phone_number_updates(self):
        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            self.assertIsNone(self.get_case_verified_number(case))

            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            self.assertIsNone(self.get_case_verified_number(case))

            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertPhoneNumberDetails(case, '99987658765', None, None)
            pk = self.get_case_verified_number(case).pk

            case = self.set_case_property(case, 'contact_phone_number', '99987698769')
            self.assertPhoneNumberDetails(case, '99987698769', None, None, pk=pk)

            case = self.set_case_property(case, 'contact_backend_id', 'sms-backend')
            self.assertPhoneNumberDetails(case, '99987698769', 'sms-backend', None, pk=pk)

            case = self.set_case_property(case, 'contact_ivr_backend_id', 'ivr-backend')
            self.assertPhoneNumberDetails(case, '99987698769', 'sms-backend', 'ivr-backend', pk=pk)

            # If nothing changes, the phone entry should not be saved
            with patch('corehq.apps.sms.models.PhoneNumber.save') as mock_save:
                case = self.set_case_property(case, 'abc', 'def')
                mock_save.assert_not_called()

            # If phone entry is ahead of the case in terms of contact_last_modified, no update should happen
            v = self.get_case_verified_number(case)
            v.contact_last_modified += timedelta(days=1)
            v.save()

            with patch('corehq.apps.sms.models.PhoneNumber.save') as mock_save:
                case = self.set_case_property(case, 'contact_phone_number', '99912341234')
                mock_save.assert_not_called()

    @run_with_all_backends
    def test_close_case(self):
        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_verified_number(case))

            update_case(self.domain, case.case_id, close=True)
            self.assertIsNone(self.get_case_verified_number(case))

    @run_with_all_backends
    def test_case_soft_delete(self):
        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_verified_number(case))

            tag_cases_as_deleted_and_remove_indices(self.domain, [case.case_id], '123', datetime.utcnow())
            self.assertIsNone(self.get_case_verified_number(case))

    @run_with_all_backends
    def test_case_zero_phone_number(self):
        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_verified_number(case))

            case = self.set_case_property(case, 'contact_phone_number', '0')
            self.assertIsNone(self.get_case_verified_number(case))

    @run_with_all_backends
    def test_invalid_phone_format(self):
        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_verified_number(case))

            case = self.set_case_property(case, 'contact_phone_number', 'xyz')
            self.assertIsNone(self.get_case_verified_number(case))

    @run_with_all_backends
    def test_phone_number_already_in_use(self):
        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case1, \
                create_test_case(self.domain, 'participant', 'test2', drop_signals=False) as case2:
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
        v1 = PhoneNumber(verified=True)
        v2 = PhoneNumber(verified=False)

        self.assertIsNone(PhoneNumber._filter_pending(None, include_pending=True))
        self.assertIsNone(PhoneNumber._filter_pending(None, include_pending=False))

        self.assertEqual(v1, PhoneNumber._filter_pending(v1, include_pending=False))
        self.assertIsNone(PhoneNumber._filter_pending(v2, include_pending=False))

        self.assertEqual(v1, PhoneNumber._filter_pending(v1, include_pending=True))
        self.assertEqual(v2, PhoneNumber._filter_pending(v2, include_pending=True))


class SQLPhoneNumberTestCase(TestCase):

    def setUp(self):
        self.domain = 'sql-phone-number-test'
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

    def delete_objects(self, result):
        for obj in result:
            # Delete and clear cache
            obj.delete()

    def tearDown(self):
        self.delete_objects(PhoneNumber.objects.filter(domain=self.domain))
        self.delete_objects(SQLMobileBackend.objects.filter(domain=self.domain))
        SQLMobileBackendMapping.objects.filter(domain=self.domain).delete()
        self.domain_obj.delete()

    def test_backend(self):
        backend1 = SQLTestSMSBackend.objects.create(
            hq_api_id=SQLTestSMSBackend.get_api_id(),
            is_global=False,
            domain=self.domain,
            name='BACKEND1'
        )

        backend2 = SQLTestSMSBackend.objects.create(
            hq_api_id=SQLTestSMSBackend.get_api_id(),
            is_global=False,
            domain=self.domain,
            name='BACKEND2'
        )

        SQLMobileBackendMapping.set_default_domain_backend(self.domain, backend1)

        number = PhoneNumber(domain=self.domain, phone_number='+999123')
        self.assertEqual(number.backend, backend1)

        number.backend_id = backend2.name
        self.assertEqual(number.backend, backend2)

        number.backend_id = '  '
        self.assertEqual(number.backend, backend1)

    @run_with_all_backends
    def test_case_owner(self):
        with create_test_case(self.domain, 'participant', 'test') as case:
            number = PhoneNumber(owner_doc_type='CommCareCase', owner_id=case.case_id)
            owner = number.owner
            self.assertTrue(is_commcarecase(owner))
            self.assertEqual(owner.case_id, case.case_id)

    def test_user_owner(self):
        mobile_user = CommCareUser.create(self.domain, 'abc', 'def')
        number = PhoneNumber(owner_doc_type='CommCareUser', owner_id=mobile_user.get_id)
        owner = number.owner
        self.assertTrue(isinstance(owner, CommCareUser))
        self.assertEqual(owner.get_id, mobile_user.get_id)

        web_user = WebUser.create(self.domain, 'ghi', 'jkl')
        number = PhoneNumber(owner_doc_type='WebUser', owner_id=web_user.get_id)
        owner = number.owner
        self.assertTrue(isinstance(owner, WebUser))
        self.assertEqual(owner.get_id, web_user.get_id)

        number = PhoneNumber(owner_doc_type='X')
        self.assertIsNone(number.owner)

    def test_phone_lookup(self):
        number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True
        )

        self.assertEqual(PhoneNumber.by_phone('999123'), number)
        self.assertEqual(PhoneNumber.by_phone('+999 123'), number)
        self.assertIsNone(PhoneNumber.by_phone('999124'))

        # test cache clear on save
        number.phone_number = '999124'
        number.save()
        self.assertIsNone(PhoneNumber.by_phone('999123'))
        self.assertEqual(PhoneNumber.by_phone('999124'), number)

        # test pending
        number.verified = False
        number.save()
        self.assertIsNone(PhoneNumber.by_phone('999124'))
        self.assertEqual(PhoneNumber.by_phone('999124', include_pending=True), number)

    def test_suffix_lookup(self):
        number1 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True
        )

        number2 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999223',
            verified=True
        )

        self.assertEqual(PhoneNumber.by_suffix('1 23'), number1)
        self.assertEqual(PhoneNumber.by_suffix('2 23'), number2)
        self.assertIsNone(PhoneNumber.by_suffix('23'))

        # test update
        number1.phone_number = '999124'
        number1.save()
        number2.phone_number = '999224'
        number2.save()
        self.assertIsNone(PhoneNumber.by_suffix('1 23'))
        self.assertIsNone(PhoneNumber.by_suffix('2 23'))
        self.assertEqual(PhoneNumber.by_suffix('124'), number1)
        self.assertEqual(PhoneNumber.by_suffix('224'), number2)

        # test pending
        number1.verified = False
        number1.save()
        number2.verified = False
        number2.save()
        self.assertIsNone(PhoneNumber.by_suffix('124'))
        self.assertIsNone(PhoneNumber.by_suffix('224'))
        self.assertEqual(PhoneNumber.by_suffix('124', include_pending=True), number1)
        self.assertEqual(PhoneNumber.by_suffix('224', include_pending=True), number2)

    def test_extensive_search(self):
        number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True
        )

        self.assertEqual(PhoneNumber.by_extensive_search('999123'), number)
        self.assertEqual(PhoneNumber.by_extensive_search('0999123'), number)
        self.assertEqual(PhoneNumber.by_extensive_search('00999123'), number)
        self.assertEqual(PhoneNumber.by_extensive_search('000999123'), number)
        self.assertEqual(PhoneNumber.by_extensive_search('123'), number)
        self.assertIsNone(PhoneNumber.by_extensive_search('999124'), number)

    def test_by_domain(self):
        number1 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True
        )

        number2 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999124',
            verified=False
        )

        number3 = PhoneNumber.objects.create(
            domain=self.domain + 'X',
            owner_doc_type='X',
            owner_id='X',
            phone_number='999124',
            verified=True
        )
        self.addCleanup(number3.delete)

        self.assertEqual(
            set(PhoneNumber.by_domain(self.domain)),
            set([number1, number2])
        )

        self.assertEqual(
            set(PhoneNumber.by_domain(self.domain, ids_only=True)),
            set([number1.couch_id, number2.couch_id])
        )

        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

    def test_by_owner_id(self):
        number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='owner1',
            phone_number='999123',
            verified=True
        )

        [lookup] = PhoneNumber.by_owner_id('owner1')
        self.assertEqual(lookup, number)

        # test cache clear
        number.owner_id = 'owner2'
        number.save()
        self.assertEqual(PhoneNumber.by_owner_id('owner1').count(), 0)
        [lookup] = PhoneNumber.by_owner_id('owner2')
        self.assertEqual(lookup, number)

        number.verified = False
        number.save()
        [lookup] = PhoneNumber.by_owner_id('owner2')
        self.assertFalse(lookup.verified)
