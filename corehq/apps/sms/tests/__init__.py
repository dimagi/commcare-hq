#from .inbound_handlers import *
from .opt_tests import *
from .migration import *
from .test_dbaccessors import *
from .test_all_backends import *
from .test_backend_migration import *
from .update_location_keyword_test import *

from corehq.apps.domain.calculations import num_mobile_users
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms_to_verified_number, send_sms_with_backend, send_sms_with_backend_name
from corehq.apps.sms.mixin import (SMSBackend, BadSMSConfigException,
    MobileBackend, apply_leniency)
from corehq.apps.sms.models import CommConnectCase, SQLMobileBackendMapping, SQLMobileBackend, MobileBackendInvitation
from corehq.apps.sms.util import get_contact
from corehq.apps.sms.tests.util import BaseSMSTest
from corehq.messaging.smsbackends.test.models import TestSMSBackend, SQLTestSMSBackend
from dimagi.ext.couchdbkit import *
from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from django.contrib.sites.models import Site
from corehq.apps.users.util import format_username
from django.conf import settings
from django.test import TestCase
from corehq.apps.accounting import generator
from mock import patch


class BackendInvocationDoc(Document):
    pass


class TestCaseBackend(TestSMSBackend):

    @classmethod
    def get_api_id(cls):
        return "TEST_CASE_BACKEND"

    def send(self, msg, *args, **kwargs):
        self.create_invoke_doc()
        print "***************************************************"
        print "Backend:         %s" % self.name
        print "Message To:      %s" % msg.phone_number
        print "Message Content: %s" % msg.text
        print "***************************************************"

    def get_invoke_doc_id(self):
        return "SEND-INVOKED-FROM-%s" % self._id

    def create_invoke_doc(self):
        if not self.invoke_doc_exists():
            doc = BackendInvocationDoc(_id=self.get_invoke_doc_id())
            doc.save()

    def delete_invoke_doc(self):
        try:
            doc = BackendInvocationDoc.get(self.get_invoke_doc_id())
            doc.delete()
        except ResourceNotFound:
            pass

    def invoke_doc_exists(self):
        try:
            BackendInvocationDoc.get(self.get_invoke_doc_id())
            return True
        except ResourceNotFound:
            return False


class BackendTestCase(BaseSMSTest):
    def get_or_create_site(self):
        site, created = Site.objects.get_or_create(id=settings.SITE_ID)
        if created:
            site.domain = 'localhost'
            site.name = 'localhost'
            site.save()
        return (site, created)

    def setUp(self):
        super(BackendTestCase, self).setUp()

        self.domain = "test-domain"
        self.domain2 = "test-domain2"

        self.site, self.site_created = self.get_or_create_site()

        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

        self.create_account_and_subscription(self.domain_obj.name)
        self.domain_obj = Domain.get(self.domain_obj._id) # Prevent resource conflict

        self.backend1 = SQLTestSMSBackend.objects.create(
            name='BACKEND1',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        self.backend2 = SQLTestSMSBackend.objects.create(
            name='BACKEND2',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        self.backend3 = SQLTestSMSBackend.objects.create(
            name='BACKEND3',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        self.backend4 = SQLTestSMSBackend.objects.create(
            name='BACKEND4',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        self.backend5 = SQLTestSMSBackend.objects.create(
            name='BACKEND5',
            domain=self.domain,
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        self.backend6 = SQLTestSMSBackend.objects.create(
            name='BACKEND6',
            domain=self.domain2,
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        self.backend6.set_shared_domains([self.domain])

        self.backend7 = SQLTestSMSBackend.objects.create(
            name='BACKEND7',
            domain=self.domain2,
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        self.backend8 = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            domain=self.domain,
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        self.backend9 = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            domain=self.domain2,
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        self.backend9.set_shared_domains([self.domain])

        self.backend10 = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        self.backend_mapping1 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='*',
            backend=self.backend1
        )

        self.backend_mapping2 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='1',
            backend=self.backend2
        )

        self.backend_mapping3 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='91',
            backend=self.backend3
        )

        self.backend_mapping4 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='265',
            backend=self.backend4
        )

        self.backend_mapping5 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='256',
            backend=self.backend5
        )

        self.backend_mapping6 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='25670',
            backend=self.backend6
        )

        self.backend_mapping7 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='25675',
            backend=self.backend7
        )

        self.case = CommCareCase(domain=self.domain)
        self.case.set_case_property('contact_phone_number', '15551234567')
        self.case.set_case_property('contact_phone_number_is_verified', '1')
        self.case.save()

        self.contact = CommConnectCase.wrap(self.case.to_json())

    def tearDown(self):
        for obj in (
            list(MobileBackendInvitation.objects.all()) +
            list(SQLMobileBackendMapping.objects.all())
        ):
            # For now we can't do bulk delete because we need to have the
            # delete sync with couch
            obj.delete()

        self.backend1.delete()
        self.backend2.delete()
        self.backend3.delete()
        self.backend4.delete()
        self.backend5.delete()
        self.backend6.delete()
        self.backend7.delete()
        self.backend8.delete()
        self.backend9.delete()
        self.backend10.delete()

        self.contact.delete_verified_number()
        self.case.delete()
        self.domain_obj.delete()

        if self.site_created:
            self.site.delete()

        super(BackendTestCase, self).tearDown()

    def test_multiple_country_prefixes(self):
        self.assertEqual(
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '256800000000'
            ).pk,
            self.backend5.pk
        )
        self.assertEqual(
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '256700000000'
            ).pk,
            self.backend6.pk
        )
        self.assertEqual(
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '256750000000'
            ).pk,
            self.backend7.pk
        )

    def __test_global_backend_map(self):
        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms(self.domain, None, '15551234567', 'Test for BACKEND2'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend2.pk)

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms(self.domain, None, '9100000000', 'Test for BACKEND3'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend3.pk)

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms(self.domain, None, '26500000000', 'Test for BACKEND4'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend4.pk)

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms(self.domain, None, '25800000000', 'Test for BACKEND1'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend1.pk)

    def __test_domain_default(self):
        # Test overriding with domain-level backend
        SQLMobileBackendMapping.set_default_domain_backend(self.domain, self.backend5)

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms(self.domain, None, '15551234567', 'Test for BACKEND5'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend5.pk)

    def __test_shared_backend(self):
        # Test use of backend that another domain owns but has granted access
        SQLMobileBackendMapping.set_default_domain_backend(self.domain, self.backend6)

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms(self.domain, None, '25800000000', 'Test for BACKEND6'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend6.pk)

        # Test trying to use a backend that another domain owns but has not granted access
        SQLMobileBackendMapping.set_default_domain_backend(self.domain, self.backend7)

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertFalse(send_sms(self.domain, None, '25800000000', 'Test Unauthorized'))
        self.assertEqual(mock_send.call_count, 0)

    def __test_verified_number_with_map(self):
        # Test sending to verified number with backend map
        SQLMobileBackendMapping.unset_default_domain_backend(self.domain)

        verified_number = self.contact.get_verified_number()
        self.assertTrue(verified_number is not None)
        self.assertTrue(verified_number.backend_id is None)
        self.assertEqual(verified_number.phone_number, '15551234567')

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms_to_verified_number(verified_number, 'Test for BACKEND2'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend2.pk)

        # Test sending to verified number with default domain backend
        SQLMobileBackendMapping.set_default_domain_backend(self.domain, self.backend5)

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms_to_verified_number(verified_number, 'Test for BACKEND5'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend5.pk)

    def __test_contact_level_backend(self):
        # Test sending to verified number with a contact-level backend owned by the domain
        self.case.set_case_property('contact_backend_id', 'BACKEND')
        self.case.save()
        self.contact = CommConnectCase.wrap(self.case.to_json())
        verified_number = self.contact.get_verified_number()
        self.assertTrue(verified_number is not None)
        self.assertEqual(verified_number.backend_id, 'BACKEND')
        self.assertEqual(verified_number.phone_number, '15551234567')

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms_to_verified_number(verified_number, 'Test for domain BACKEND'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend8.pk)

        # Test sending to verified number with a contact-level backend granted to the domain by another domain
        self.backend8.name = 'BACKEND8'
        self.backend8.save()

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms_to_verified_number(verified_number, 'Test for shared domain BACKEND'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend9.pk)

        # Test sending to verified number with a contact-level global backend
        self.backend9.name = 'BACKEND9'
        self.backend9.save()

        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms_to_verified_number(verified_number, 'Test for global BACKEND'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend10.pk)

        # Test raising exception if contact-level backend is not found
        self.backend10.name = 'BACKEND10'
        self.backend10.save()

        with self.assertRaises(BadSMSConfigException):
            send_sms_to_verified_number(verified_number, 'Test for unknown BACKEND')

    def __test_send_sms_with_backend(self):
        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms_with_backend(self.domain, '+15551234567', 'Test for BACKEND3', self.backend3.couch_id))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend3.pk)

    def __test_send_sms_with_backend_name(self):
        with patch(
            'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send',
            autospec=True
        ) as mock_send:
            self.assertTrue(send_sms_with_backend_name(self.domain, '+15551234567', 'Test for BACKEND3', 'BACKEND3'))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args[0][0].pk, self.backend3.pk)

    def test_choosing_appropriate_backend_for_sending(self):
        self.__test_global_backend_map()
        self.__test_domain_default()
        self.__test_shared_backend()
        self.__test_verified_number_with_map()
        self.__test_contact_level_backend()
        self.__test_send_sms_with_backend()
        self.__test_send_sms_with_backend_name()

    def test_sms_registration(self):
        formatted_username = format_username("tester", self.domain)

        incoming("+9991234567", "JOIN {} WORKER tester".format(self.domain), "TEST_CASE_BACKEND")
        # Test without mobile worker registration enabled
        self.assertIsNone(CommCareUser.get_by_username(formatted_username))

        # Enable mobile worker registration
        setattr(self.domain_obj, "sms_mobile_worker_registration_enabled", True)
        self.domain_obj.save()

        incoming("+9991234567", "JOIN {} WORKER tester".format(self.domain), "TEST_CASE_BACKEND")
        self.assertIsNotNone(CommCareUser.get_by_username(formatted_username))

        # Test a duplicate registration
        prev_num_users = num_mobile_users(self.domain)
        incoming("+9991234568", "JOIN {} WORKER tester".format(self.domain), "TEST_CASE_BACKEND")
        current_num_users = num_mobile_users(self.domain)
        self.assertEqual(prev_num_users, current_num_users)


class TestUtilFunctions(TestCase):
    def setUp(self):
        self.case = CommCareCase(domain='test-domain', name='test-case')
        self.case.save()

        self.user = CommCareUser.create('test-domain', 'test-user', '123')

    def test_get_contact(self):
        contact = get_contact(self.case.get_id)
        self.assertEqual(contact.get_id, self.case.get_id)
        self.assertTrue(isinstance(contact, CommConnectCase))

        contact = get_contact(self.user.get_id)
        self.assertEqual(contact.get_id, self.user.get_id)
        self.assertTrue(isinstance(contact, CommCareUser))

        try:
            get_contact('this-id-should-not-be-found')
        except Exception:
            pass
        else:
            self.assertTrue(False)

    def test_apply_leniency(self):
        self.assertEqual('16175551234', apply_leniency(' 1 (617) 555-1234 '))
        self.assertEqual('16175551234', apply_leniency(' 1.617.555.1234 '))
        self.assertEqual('16175551234', apply_leniency(' +1 617 555 1234 '))

    def tearDown(self):
        self.case.delete()
        self.user.delete()
