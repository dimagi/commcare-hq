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
from corehq.apps.sms.models import CommConnectCase
from corehq.apps.sms.util import get_contact
from corehq.apps.sms.tests.util import BaseSMSTest
from corehq.messaging.smsbackends.test.models import TestSMSBackend
from dimagi.ext.couchdbkit import *
from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from django.contrib.sites.models import Site
from corehq.apps.users.util import format_username
from django.conf import settings
from django.test import TestCase
from corehq.apps.accounting import generator


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

        self.backend1 = TestCaseBackend(name="BACKEND1",is_global=True)
        self.backend1.save()

        self.backend2 = TestCaseBackend(name="BACKEND2",is_global=True)
        self.backend2.save()

        self.backend3 = TestCaseBackend(name="BACKEND3",is_global=True)
        self.backend3.save()

        self.backend4 = TestCaseBackend(name="BACKEND4",is_global=True)
        self.backend4.save()

        self.backend5 = TestCaseBackend(name="BACKEND5",domain=self.domain,is_global=False,authorized_domains=[])
        self.backend5.save()

        self.backend6 = TestCaseBackend(name="BACKEND6",domain=self.domain2,is_global=False,authorized_domains=[self.domain])
        self.backend6.save()

        self.backend7 = TestCaseBackend(name="BACKEND7",domain=self.domain2,is_global=False,authorized_domains=[])
        self.backend7.save()
        
        self.backend8 = TestCaseBackend(name="BACKEND",domain=self.domain,is_global=False,authorized_domains=[])
        self.backend8.save()

        self.backend9 = TestCaseBackend(name="BACKEND",domain=self.domain2,is_global=False,authorized_domains=[self.domain])
        self.backend9.save()

        self.backend10 = TestCaseBackend(name="BACKEND",is_global=True)
        self.backend10.save()

        self.backend_mapping1 = BackendMapping(is_global=True,prefix="*",backend_id=self.backend1._id)
        self.backend_mapping1.save()

        self.backend_mapping2 = BackendMapping(is_global=True,prefix="1",backend_id=self.backend2._id)
        self.backend_mapping2.save()

        self.backend_mapping3 = BackendMapping(is_global=True,prefix="91",backend_id=self.backend3._id)
        self.backend_mapping3.save()

        self.backend_mapping4 = BackendMapping(is_global=True,prefix="265",backend_id=self.backend4._id)
        self.backend_mapping4.save()

        self.backend_mapping5 = BackendMapping(is_global=True, prefix="256", backend_id=self.backend5._id)
        self.backend_mapping5.save()

        self.backend_mapping6 = BackendMapping(is_global=True, prefix="25670", backend_id=self.backend6._id)
        self.backend_mapping6.save()

        self.backend_mapping7 = BackendMapping(is_global=True, prefix="25675", backend_id=self.backend7._id)
        self.backend_mapping7.save()

        self.case = CommCareCase(domain=self.domain)
        self.case.set_case_property("contact_phone_number","15551234567")
        self.case.set_case_property("contact_phone_number_is_verified", "1")
        self.case.save()

        self.contact = CommConnectCase.wrap(self.case.to_json())

        settings.SMS_LOADED_BACKENDS.append("corehq.apps.sms.tests.TestCaseBackend")

    def tearDown(self):
        self.backend1.delete_invoke_doc()
        self.backend1.delete()
        self.backend_mapping1.delete()

        self.backend2.delete_invoke_doc()
        self.backend2.delete()
        self.backend_mapping2.delete()

        self.backend3.delete_invoke_doc()
        self.backend3.delete()
        self.backend_mapping3.delete()

        self.backend4.delete_invoke_doc()
        self.backend4.delete()
        self.backend_mapping4.delete()

        self.backend5.delete_invoke_doc()
        self.backend5.delete()
        self.backend_mapping5.delete()

        self.backend6.delete_invoke_doc()
        self.backend6.delete()
        self.backend_mapping6.delete()

        self.backend7.delete_invoke_doc()
        self.backend7.delete()
        self.backend_mapping7.delete()

        self.contact.delete_verified_number()
        self.case.delete()

        self.domain_obj.delete()

        if self.site_created:
            self.site.delete()

        settings.SMS_LOADED_BACKENDS.pop()

        super(BackendTestCase, self).tearDown()

    def test_multiple_country_prefixes(self):
        self.assertEqual(MobileBackend.auto_load('256800000000')._id, self.backend5._id)
        self.assertEqual(MobileBackend.auto_load('256700000000')._id, self.backend6._id)
        self.assertEqual(MobileBackend.auto_load('256750000000')._id, self.backend7._id)

    def test_backend(self):
        # Test the backend map

        self.assertTrue(send_sms(self.domain, None, "15551234567", "Test for BACKEND2"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertTrue(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend2.delete_invoke_doc()
        self.assertFalse(self.backend2.invoke_doc_exists())

        self.assertTrue(send_sms(self.domain, None, "9100000000", "Test for BACKEND3"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertTrue(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend3.delete_invoke_doc()
        self.assertFalse(self.backend3.invoke_doc_exists())

        self.assertTrue(send_sms(self.domain, None, "26500000000", "Test for BACKEND4"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertTrue(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend4.delete_invoke_doc()
        self.assertFalse(self.backend4.invoke_doc_exists())

        self.assertTrue(send_sms(self.domain, None, "25800000000", "Test for BACKEND1"))
        self.assertTrue(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend1.delete_invoke_doc()
        self.assertFalse(self.backend1.invoke_doc_exists())

        # Test overriding with a domain-level backend

        self.domain_obj = Domain.get(self.domain_obj._id)  # Prevent resource conflict
        self.domain_obj.default_sms_backend_id = self.backend5._id
        self.domain_obj.save()

        self.assertTrue(send_sms(self.domain, None, "15551234567", "Test for BACKEND5"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertTrue(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend5.delete_invoke_doc()
        self.assertFalse(self.backend5.invoke_doc_exists())

        # Test use of backend that another domain owns but has granted access

        self.domain_obj.default_sms_backend_id = self.backend6._id
        self.domain_obj.save()

        self.assertTrue(send_sms(self.domain, None, "25800000000", "Test for BACKEND6"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertTrue(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend6.delete_invoke_doc()
        self.assertFalse(self.backend6.invoke_doc_exists())

        # Test backend access control

        self.domain_obj.default_sms_backend_id = self.backend7._id
        self.domain_obj.save()

        self.assertFalse(send_sms(self.domain, None, "25800000000", "Test for BACKEND7"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())

        # Test sending to verified number with backend map

        self.domain_obj.default_sms_backend_id = None
        self.domain_obj.save()

        verified_number = self.contact.get_verified_number()
        self.assertTrue(verified_number is not None)
        self.assertTrue(verified_number.backend_id is None)
        self.assertEqual(verified_number.phone_number, "15551234567")

        self.assertTrue(send_sms_to_verified_number(verified_number, "Test for BACKEND2"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertTrue(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend2.delete_invoke_doc()
        self.assertFalse(self.backend2.invoke_doc_exists())

        # Test sending to verified number with default domain backend

        self.domain_obj.default_sms_backend_id = self.backend5._id
        self.domain_obj.save()

        self.assertTrue(send_sms_to_verified_number(verified_number, "Test for BACKEND5"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertTrue(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertFalse(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend5.delete_invoke_doc()
        self.assertFalse(self.backend5.invoke_doc_exists())

        # Test sending to verified number with a contact-level backend owned by the domain

        self.case.set_case_property("contact_backend_id", "BACKEND")
        self.case.save()
        self.contact = CommConnectCase.wrap(self.case.to_json())
        verified_number = self.contact.get_verified_number()
        self.assertTrue(verified_number is not None)
        self.assertEqual(verified_number.backend_id, "BACKEND")
        self.assertEqual(verified_number.phone_number, "15551234567")

        self.assertTrue(send_sms_to_verified_number(verified_number, "Test for BACKEND"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertTrue(self.backend8.invoke_doc_exists())
        self.assertFalse(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend8.delete_invoke_doc()
        self.assertFalse(self.backend8.invoke_doc_exists())

        # Test sending to verified number with a contact-level backend granted to the domain by another domain

        self.backend8.delete()

        self.assertTrue(send_sms_to_verified_number(verified_number, "Test for BACKEND"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertTrue(self.backend9.invoke_doc_exists())
        self.assertFalse(self.backend10.invoke_doc_exists())
        self.backend9.delete_invoke_doc()
        self.assertFalse(self.backend9.invoke_doc_exists())

        # Test sending to verified number with a contact-level global backend

        self.backend9.delete()

        self.assertTrue(send_sms_to_verified_number(verified_number, "Test for BACKEND"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertFalse(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.assertTrue(self.backend10.invoke_doc_exists())
        self.backend10.delete_invoke_doc()
        self.assertFalse(self.backend10.invoke_doc_exists())

        # Test raising exception if contact-level backend is not found

        self.backend10.delete()

        try:
            self.assertTrue(send_sms_to_verified_number(verified_number, "Test for BACKEND"))
        except BadSMSConfigException:
            pass
        else:
            self.assertTrue(False)

        # Test send_sms_with_backend

        self.assertTrue(send_sms_with_backend(self.domain, "+15551234567", "Test for BACKEND3", self.backend3._id))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertTrue(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.backend3.delete_invoke_doc()
        self.assertFalse(self.backend3.invoke_doc_exists())

        # Test send_sms_with_backend_name

        self.assertTrue(send_sms_with_backend_name(self.domain, "+15551234567", "Test for BACKEND3", "BACKEND3"))
        self.assertFalse(self.backend1.invoke_doc_exists())
        self.assertFalse(self.backend2.invoke_doc_exists())
        self.assertTrue(self.backend3.invoke_doc_exists())
        self.assertFalse(self.backend4.invoke_doc_exists())
        self.assertFalse(self.backend5.invoke_doc_exists())
        self.assertFalse(self.backend6.invoke_doc_exists())
        self.assertFalse(self.backend7.invoke_doc_exists())
        self.backend3.delete_invoke_doc()
        self.assertFalse(self.backend3.invoke_doc_exists())

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
