from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import update_case
from corehq.apps.sms.mixin import PhoneNumberInUseException
from corehq.apps.sms.models import (SQLMobileBackend, SQLMobileBackendMapping,
    PhoneNumber)
from corehq.apps.sms.tasks import delete_phone_numbers_for_owners, sync_case_phone_number
from corehq.apps.sms.tests.util import delete_domain_phone_numbers
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.tasks import tag_cases_as_deleted_and_remove_indices
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from datetime import datetime, timedelta
from django.test import TestCase
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import is_commcarecase
from corehq.util.test_utils import create_test_case
from mock import patch


class PhoneNumberCacheClearTestCase(TestCase):

    def assertNoMatch(self, phone_search, suffix_search, owner_id_search):
        self.assertIsNone(PhoneNumber.get_two_way_number(phone_search))
        self.assertIsNone(PhoneNumber.get_two_way_number_by_suffix(suffix_search))
        self.assertEqual(PhoneNumber.by_owner_id(owner_id_search), [])

    def assertPhoneNumbersEqual(self, phone1, phone2):
        for field in phone1._meta.fields:
            self.assertEqual(getattr(phone1, field.name), getattr(phone2, field.name))

    def assertMatch(self, match, phone_search, suffix_search, owner_id_search):
        lookedup = PhoneNumber.get_two_way_number(phone_search)
        self.assertPhoneNumbersEqual(match, lookedup)

        lookedup = PhoneNumber.get_two_way_number_by_suffix(suffix_search)
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
            pending_verification=False,
            is_two_way=True,
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
        delete_domain_phone_numbers(self.domain)

    def set_case_property(self, case, property_name, value):
        update_case(self.domain, case.case_id, case_properties={property_name: value})
        return CaseAccessors(self.domain).get_case(case.case_id)

    def get_case_phone_number(self, case):
        return case.get_phone_number()

    def assertPhoneNumberDetails(self, case, phone_number, sms_backend_id, ivr_backend_id,
            verified, pending_verification, is_two_way, pk=None):
        v = self.get_case_phone_number(case)
        self.assertEqual(v.domain, case.domain)
        self.assertEqual(v.owner_doc_type, case.doc_type)
        self.assertEqual(v.owner_id, case.case_id)
        self.assertEqual(v.phone_number, phone_number)
        self.assertEqual(v.backend_id, sms_backend_id)
        self.assertEqual(v.ivr_backend_id, ivr_backend_id)
        self.assertEqual(v.verified, verified)
        self.assertEqual(v.pending_verification, pending_verification)
        self.assertEqual(v.is_two_way, is_two_way)
        self.assertEqual(v.contact_last_modified, case.server_modified_on)

        if pk:
            self.assertEqual(v.pk, pk)

    @run_with_all_backends
    def test_case_phone_number_updates(self):
        extra_number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            self.assertIsNone(self.get_case_phone_number(case))

            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            self.assertPhoneNumberDetails(case, '99987658765', None, None, False, False, False)
            pk = self.get_case_phone_number(case).pk
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertPhoneNumberDetails(case, '99987658765', None, None, True, False, True, pk=pk)
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            case = self.set_case_property(case, 'contact_phone_number', '99987698769')
            self.assertPhoneNumberDetails(case, '99987698769', None, None, True, False, True)
            pk = self.get_case_phone_number(case).pk
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            case = self.set_case_property(case, 'contact_backend_id', 'sms-backend')
            self.assertPhoneNumberDetails(case, '99987698769', 'sms-backend', None, True, False, True, pk=pk)
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            case = self.set_case_property(case, 'contact_ivr_backend_id', 'ivr-backend')
            self.assertPhoneNumberDetails(case, '99987698769', 'sms-backend', 'ivr-backend', True, False, True,
                pk=pk)
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            # If phone entry is ahead of the case in terms of contact_last_modified, no update should happen
            v = self.get_case_phone_number(case)
            v.contact_last_modified += timedelta(days=1)
            v.save()

            with patch('corehq.apps.sms.models.PhoneNumber.save') as mock_save:
                case = self.set_case_property(case, 'contact_phone_number', '99912341234')
                self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)
                mock_save.assert_not_called()

        self.assertEqual(PhoneNumber.get_two_way_number('999123'), extra_number)

    @run_with_all_backends
    def test_close_case(self):
        extra_number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_phone_number(case))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            update_case(self.domain, case.case_id, close=True)
            self.assertIsNone(self.get_case_phone_number(case))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        self.assertEqual(PhoneNumber.get_two_way_number('999123'), extra_number)

    @run_with_all_backends
    def test_case_soft_delete(self):
        extra_number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_phone_number(case))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            tag_cases_as_deleted_and_remove_indices(self.domain, [case.case_id], '123', datetime.utcnow())
            self.assertIsNone(self.get_case_phone_number(case))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        self.assertEqual(PhoneNumber.get_two_way_number('999123'), extra_number)

    @run_with_all_backends
    def test_case_zero_phone_number(self):
        extra_number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_phone_number(case))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            case = self.set_case_property(case, 'contact_phone_number', '0')
            self.assertIsNone(self.get_case_phone_number(case))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        self.assertEqual(PhoneNumber.get_two_way_number('999123'), extra_number)

    @run_with_all_backends
    def test_invalid_phone_format(self):
        extra_number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '99987658765')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            self.assertIsNotNone(self.get_case_phone_number(case))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            case = self.set_case_property(case, 'contact_phone_number', 'xyz')
            self.assertIsNone(self.get_case_phone_number(case))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

        self.assertEqual(PhoneNumber.get_two_way_number('999123'), extra_number)

    @run_with_all_backends
    def test_phone_number_already_in_use(self):
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 0)

        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case1, \
                create_test_case(self.domain, 'participant', 'test2', drop_signals=False) as case2:
            case1 = self.set_case_property(case1, 'contact_phone_number', '99987658765')
            case1 = self.set_case_property(case1, 'contact_phone_number_is_verified', '1')

            case2 = self.set_case_property(case2, 'contact_phone_number', '99987698769')
            case2 = self.set_case_property(case2, 'contact_phone_number_is_verified', '1')

            self.assertIsNotNone(self.get_case_phone_number(case1))
            self.assertIsNotNone(self.get_case_phone_number(case2))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            case2 = self.set_case_property(case2, 'contact_phone_number', '99987658765')

            self.assertIsNotNone(self.get_case_phone_number(case1))
            self.assertIsNotNone(self.get_case_phone_number(case2))
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

            self.assertPhoneNumberDetails(case1, '99987658765', None, None, True, False, True)
            self.assertPhoneNumberDetails(case2, '99987658765', None, None, False, False, False)

    @run_with_all_backends
    def test_multiple_entries(self):
        extra_number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999124',
            verified=False,
            pending_verification=False,
            is_two_way=False
        )

        with create_test_case(self.domain, 'participant', 'test1', drop_signals=False) as case:
            case = self.set_case_property(case, 'contact_phone_number', '999124')
            case = self.set_case_property(case, 'contact_phone_number_is_verified', '1')
            case.create_phone_entry('999125')
            self.assertEqual(PhoneNumber.objects.count(), 3)

            sync_case_phone_number(case)
            self.assertEqual(PhoneNumber.objects.count(), 2)

            number1 = PhoneNumber.objects.get(pk=extra_number.pk)
            self.assertEqual(number1.owner_id, 'X')

            number2 = PhoneNumber.objects.get(owner_id=case.case_id)
            self.assertTrue(number2.verified)
            self.assertTrue(number2.is_two_way)
            self.assertFalse(number2.pending_verification)


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
        self.addCleanup(web_user.delete)
        number = PhoneNumber(owner_doc_type='WebUser', owner_id=web_user.get_id)
        owner = number.owner
        self.assertTrue(isinstance(owner, WebUser))
        self.assertEqual(owner.get_id, web_user.get_id)

        number = PhoneNumber(owner_doc_type='X')
        self.assertIsNone(number.owner)

    def test_get_two_way_number(self):
        number1 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )

        PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=False,
            pending_verification=False,
            is_two_way=False
        )

        self.assertEqual(PhoneNumber.get_two_way_number('999123'), number1)
        self.assertEqual(PhoneNumber.get_two_way_number('+999 123'), number1)
        self.assertIsNone(PhoneNumber.get_two_way_number('999124'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999123'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999124'))
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

        # test cache clear on save
        number1.phone_number = '999124'
        number1.save()
        self.assertIsNone(PhoneNumber.get_two_way_number('999123'))
        self.assertEqual(PhoneNumber.get_two_way_number('999124'), number1)
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999123'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999124'))
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

        # test cache clear on delete
        number1.delete()
        self.assertIsNone(PhoneNumber.get_two_way_number('999123'))
        self.assertIsNone(PhoneNumber.get_two_way_number('999124'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999123'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999124'))
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

    def test_get_number_pending_verification(self):
        number1 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=False,
            pending_verification=True,
            is_two_way=False
        )

        PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=False,
            pending_verification=False,
            is_two_way=False
        )

        self.assertIsNone(PhoneNumber.get_two_way_number('999123'))
        self.assertIsNone(PhoneNumber.get_two_way_number('999124'))
        self.assertEqual(PhoneNumber.get_number_pending_verification('999123'), number1)
        self.assertEqual(PhoneNumber.get_number_pending_verification('+999 123'), number1)
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999124'))
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

        # test cache clear on save
        number1.phone_number = '999124'
        number1.save()
        self.assertIsNone(PhoneNumber.get_two_way_number('999123'))
        self.assertIsNone(PhoneNumber.get_two_way_number('999124'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999123'))
        self.assertEqual(PhoneNumber.get_number_pending_verification('999124'), number1)
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

        # test promotion to two-way
        number1.set_two_way()
        number1.set_verified()
        number1.save()
        self.assertIsNone(PhoneNumber.get_two_way_number('999123'))
        self.assertEqual(PhoneNumber.get_two_way_number('999124'), number1)
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999123'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999124'))
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 2)

        # test cache clear on delete
        number1.delete()
        self.assertIsNone(PhoneNumber.get_two_way_number('999123'))
        self.assertIsNone(PhoneNumber.get_two_way_number('999124'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999123'))
        self.assertIsNone(PhoneNumber.get_number_pending_verification('999124'))
        self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

    def test_suffix_lookup(self):
        number1 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )

        number2 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999223',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )

        self.assertEqual(PhoneNumber.get_two_way_number_by_suffix('1 23'), number1)
        self.assertEqual(PhoneNumber.get_two_way_number_by_suffix('2 23'), number2)
        self.assertIsNone(PhoneNumber.get_two_way_number_by_suffix('23'))

        # test update
        number1.phone_number = '999124'
        number1.save()
        number2.phone_number = '999224'
        number2.save()
        self.assertIsNone(PhoneNumber.get_two_way_number_by_suffix('1 23'))
        self.assertIsNone(PhoneNumber.get_two_way_number_by_suffix('2 23'))
        self.assertEqual(PhoneNumber.get_two_way_number_by_suffix('124'), number1)
        self.assertEqual(PhoneNumber.get_two_way_number_by_suffix('224'), number2)

    def test_extensive_search(self):
        number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )

        self.assertEqual(PhoneNumber.by_extensive_search('999123'), number)
        self.assertEqual(PhoneNumber.by_extensive_search('0999123'), number)
        self.assertEqual(PhoneNumber.by_extensive_search('00999123'), number)
        self.assertEqual(PhoneNumber.by_extensive_search('000999123'), number)
        self.assertEqual(PhoneNumber.by_extensive_search('123'), number)
        self.assertIsNone(PhoneNumber.by_extensive_search('999124'))

    def test_by_domain(self):
        number1 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )

        number2 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999124',
            verified=False,
            pending_verification=False,
            is_two_way=False
        )

        number3 = PhoneNumber.objects.create(
            domain=self.domain + 'X',
            owner_doc_type='X',
            owner_id='X',
            phone_number='999124',
            verified=True,
            pending_verification=False,
            is_two_way=True
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
            verified=True,
            pending_verification=False,
            is_two_way=True
        )

        [lookup] = PhoneNumber.by_owner_id('owner1')
        self.assertEqual(lookup, number)

        # test cache clear
        number.owner_id = 'owner2'
        number.save()
        self.assertEqual(PhoneNumber.by_owner_id('owner1'), [])
        [lookup] = PhoneNumber.by_owner_id('owner2')
        self.assertEqual(lookup, number)

        number.verified = False
        number.is_two_way = False
        number.save()
        [lookup] = PhoneNumber.by_owner_id('owner2')
        self.assertFalse(lookup.verified)
        self.assertFalse(lookup.is_two_way)

    def create_case_contact(self, phone_number):
        return create_test_case(
            self.domain,
            'participant',
            'test',
            case_properties={
                'contact_phone_number': phone_number,
                'contact_phone_number_is_verified': '1',
            },
            drop_signals=False
        )

    @run_with_all_backends
    def test_delete_phone_numbers_for_owners(self):
        with self.create_case_contact('9990001') as case1, \
                self.create_case_contact('9990002') as case2, \
                self.create_case_contact('9990003') as case3:

            self.assertEqual(len(PhoneNumber.by_owner_id(case1.case_id)), 1)
            self.assertEqual(len(PhoneNumber.by_owner_id(case2.case_id)), 1)
            self.assertEqual(len(PhoneNumber.by_owner_id(case3.case_id)), 1)
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 3)

            delete_phone_numbers_for_owners([case2.case_id, case3.case_id])
            self.assertEqual(len(PhoneNumber.by_owner_id(case1.case_id)), 1)
            self.assertEqual(len(PhoneNumber.by_owner_id(case2.case_id)), 0)
            self.assertEqual(len(PhoneNumber.by_owner_id(case3.case_id)), 0)
            self.assertEqual(PhoneNumber.count_by_domain(self.domain), 1)

    def test_verify_uniqueness(self):
        number1 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )

        number2 = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='X',
            phone_number='999123',
            verified=False,
            pending_verification=False,
            is_two_way=False
        )

        # Raises no exception
        number1.verify_uniqueness()

        # Raises PhoneNumberInUseException
        with self.assertRaises(PhoneNumberInUseException):
            number2.verify_uniqueness()


class TestUserPhoneNumberSync(TestCase):

    def setUp(self):
        self.domain = 'user-phone-number-test'
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()
        self.mobile_worker1 = CommCareUser.create(self.domain, 'mobile1', 'mobile1')
        self.mobile_worker2 = CommCareUser.create(self.domain, 'mobile2', 'mobile2')

    def tearDown(self):
        delete_domain_phone_numbers(self.domain)
        self.domain_obj.delete()

    def assertPhoneEntries(self, user, phone_numbers):
        entries = user.get_phone_entries()
        self.assertEqual(len(entries), len(phone_numbers))
        self.assertEqual(set(entries.keys()), set(phone_numbers))

    def testSync(self):
        extra_number = PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type='X',
            owner_id='owner1',
            phone_number='999123',
            verified=True,
            pending_verification=False,
            is_two_way=True
        )

        user = self.mobile_worker1
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 1)

        user.phone_numbers = ['9990001']
        user.save()
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 2)
        self.assertPhoneEntries(user, ['9990001'])

        before = user.get_phone_entries()['9990001']

        user.phone_numbers = ['9990001', '9990002']
        user.save()
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 3)
        self.assertPhoneEntries(user, ['9990001', '9990002'])

        after = user.get_phone_entries()['9990001']
        self.assertEqual(before.pk, after.pk)

        user.phone_numbers = ['9990002']
        user.save()
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 2)
        self.assertPhoneEntries(user, ['9990002'])

        self.assertEqual(PhoneNumber.get_two_way_number('999123'), extra_number)

    def testRetire(self):
        self.mobile_worker1.phone_numbers = ['9990001']
        self.mobile_worker1.save()
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 1)
        self.assertPhoneEntries(self.mobile_worker1, ['9990001'])

        self.mobile_worker2.phone_numbers = ['9990002']
        self.mobile_worker2.save()
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 2)
        self.assertPhoneEntries(self.mobile_worker2, ['9990002'])

        self.mobile_worker1.retire()
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 1)
        self.assertPhoneEntries(self.mobile_worker2, ['9990002'])


class TestGenericContactMethods(TestCase):

    def setUp(self):
        self.domain = 'contact-phone-number-test'
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()
        self.mobile_worker1 = CommCareUser.create(self.domain, 'mobile1', 'mobile1')
        self.mobile_worker2 = CommCareUser.create(self.domain, 'mobile2', 'mobile2')

    def tearDown(self):
        delete_domain_phone_numbers(self.domain)
        self.domain_obj.delete()

    def testGetOrCreate(self):
        before = self.mobile_worker1.get_or_create_phone_entry('999123')
        self.assertEqual(before.owner_doc_type, 'CommCareUser')
        self.assertEqual(before.owner_id, self.mobile_worker1.get_id)
        self.assertEqual(before.phone_number, '999123')
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 1)

        after = self.mobile_worker1.get_or_create_phone_entry('999123')
        self.assertEqual(before.pk, after.pk)
        self.assertEqual(after.owner_doc_type, 'CommCareUser')
        self.assertEqual(after.owner_id, self.mobile_worker1.get_id)
        self.assertEqual(after.phone_number, '999123')
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 1)

    def testGetPhoneEntries(self):
        number1 = self.mobile_worker1.get_or_create_phone_entry('999123')
        number2 = self.mobile_worker1.get_or_create_phone_entry('999124')
        self.mobile_worker1.get_or_create_phone_entry('999125')
        number4 = self.mobile_worker2.get_or_create_phone_entry('999126')

        number1.set_two_way()
        number2.set_pending_verification()
        number4.set_two_way()

        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 4)
        entries = self.mobile_worker1.get_phone_entries()
        self.assertEqual(set(entries.keys()), set(['999123', '999124', '999125']))

        entries = self.mobile_worker1.get_two_way_numbers()
        self.assertEqual(set(entries.keys()), set(['999123']))

    def testDelete(self):
        self.mobile_worker1.get_or_create_phone_entry('999123')
        self.mobile_worker1.get_or_create_phone_entry('999124')
        self.mobile_worker1.get_or_create_phone_entry('999125')
        self.mobile_worker2.get_or_create_phone_entry('999126')
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 4)

        self.mobile_worker1.delete_phone_entry('999124')
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 3)

        entries = self.mobile_worker1.get_phone_entries()
        self.assertEqual(set(entries.keys()), set(['999123', '999125']))

        entries = self.mobile_worker2.get_phone_entries()
        self.assertEqual(set(entries.keys()), set(['999126']))

    def testUserSyncNoChange(self):
        before = self.mobile_worker1.get_or_create_phone_entry('999123')
        before.set_two_way()
        before.set_verified()
        before.save()
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 1)

        self.mobile_worker1.phone_numbers = ['999123']
        self.mobile_worker1.save()
        self.assertEqual(PhoneNumber.by_domain(self.domain).count(), 1)

        after = self.mobile_worker1.get_phone_entries()['999123']
        self.assertEqual(before.pk, after.pk)
        self.assertTrue(after.is_two_way)
        self.assertTrue(after.verified)
        self.assertFalse(after.pending_verification)
