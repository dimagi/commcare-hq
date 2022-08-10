from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.models import Domain
from corehq.messaging.pillow import get_case_messaging_sync_pillow
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.apps.sms.api import incoming, send_sms_to_verified_number
from corehq.apps.sms.messages import MSG_OPTED_IN, MSG_OPTED_OUT, get_message
from corehq.apps.sms.models import SMS, PhoneBlacklist, PhoneNumber, SQLMobileBackendMapping, SQLMobileBackend
from corehq.apps.sms.tests.util import (
    delete_domain_phone_numbers,
    setup_default_sms_test_backend,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from testapps.test_pillowtop.utils import process_pillow_changes


class OptTestCase(DomainSubscriptionMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        super(OptTestCase, cls).setUpClass()
        cls.domain = 'opt-test'
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.sms_case_registration_enabled = True
        cls.domain_obj.save()

        cls.setup_subscription(cls.domain, SoftwarePlanEdition.ADVANCED)
        cls.backend, cls.backend_mapping = setup_default_sms_test_backend()
        cls.custom_backend = SQLTestSMSBackend.objects.create(
            name='MOBILE_BACKEND_CUSTOM_TEST',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
            opt_in_keywords=['RESTART'],
            opt_out_keywords=['RESTOP']
        )
        cls.custom_backend_mapping = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='1',
            backend=cls.custom_backend,
        )
        cls.process_pillow_changes = process_pillow_changes('DefaultChangeFeedPillow')
        cls.process_pillow_changes.add_pillow(get_case_messaging_sync_pillow())


    @classmethod
    def tearDownClass(cls):
        cls.backend_mapping.delete()
        cls.backend.delete()
        cls.custom_backend_mapping.delete()
        cls.custom_backend.delete()
        FormProcessorTestUtils.delete_all_cases(cls.domain)
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super(OptTestCase, cls).tearDownClass()

    def tearDown(self):
        PhoneBlacklist.objects.all().delete()
        SMS.objects.filter(domain=self.domain).delete()
        delete_domain_phone_numbers(self.domain)

    def get_last_sms(self, phone_number):
        return SMS.objects.filter(domain=self.domain, phone_number=phone_number).order_by('-date')[0]

    def handle_incoming(self, *args, **kwargs):
        with self.process_pillow_changes:
            incoming(*args, **kwargs)

    def test_opt_out_and_opt_in(self):
        self.assertEqual(PhoneBlacklist.objects.count(), 0)

        self.handle_incoming('99912345678', 'join opt-test', 'GVI')
        v = PhoneNumber.get_two_way_number('99912345678')
        self.assertIsNotNone(v)

        self.handle_incoming('99912345678', 'stop', 'GVI')
        self.assertEqual(PhoneBlacklist.objects.count(), 1)
        phone_number = PhoneBlacklist.objects.get(phone_number='99912345678')
        self.assertFalse(phone_number.send_sms)
        self.assertEqual(phone_number.domain, self.domain)
        self.assertIsNotNone(phone_number.last_sms_opt_out_timestamp)
        self.assertIsNone(phone_number.last_sms_opt_in_timestamp)

        sms = self.get_last_sms('+99912345678')
        self.assertEqual(sms.direction, 'O')
        self.assertEqual(sms.text, get_message(MSG_OPTED_OUT, context=('START',)))

        self.handle_incoming('99912345678', 'start', 'GVI')
        self.assertEqual(PhoneBlacklist.objects.count(), 1)
        phone_number = PhoneBlacklist.objects.get(phone_number='99912345678')
        self.assertTrue(phone_number.send_sms)
        self.assertEqual(phone_number.domain, self.domain)
        self.assertIsNotNone(phone_number.last_sms_opt_out_timestamp)
        self.assertIsNotNone(phone_number.last_sms_opt_in_timestamp)

        sms = self.get_last_sms('+99912345678')
        self.assertEqual(sms.direction, 'O')
        self.assertEqual(sms.text, get_message(MSG_OPTED_IN, context=('STOP',)))

    def test_sending_to_opted_out_number(self):
        self.assertEqual(PhoneBlacklist.objects.count(), 0)

        self.handle_incoming('99912345678', 'join opt-test', 'GVI')
        v = PhoneNumber.get_two_way_number('99912345678')
        self.assertIsNotNone(v)

        send_sms_to_verified_number(v, 'hello')
        sms = self.get_last_sms('+99912345678')
        self.assertEqual(sms.direction, 'O')
        self.assertEqual(sms.text, 'hello')

        self.handle_incoming('99912345678', 'stop', 'GVI')
        self.assertEqual(PhoneBlacklist.objects.count(), 1)
        phone_number = PhoneBlacklist.objects.get(phone_number='99912345678')
        self.assertFalse(phone_number.send_sms)

        send_sms_to_verified_number(v, 'hello')
        sms = self.get_last_sms('+99912345678')
        self.assertEqual(sms.direction, 'O')
        self.assertEqual(sms.text, 'hello')
        self.assertTrue(sms.error)
        self.assertEqual(sms.system_error_message, SMS.ERROR_PHONE_NUMBER_OPTED_OUT)

        self.handle_incoming('99912345678', 'start', 'GVI')
        self.assertEqual(PhoneBlacklist.objects.count(), 1)
        phone_number = PhoneBlacklist.objects.get(phone_number='99912345678')
        self.assertTrue(phone_number.send_sms)

        send_sms_to_verified_number(v, 'hello')
        sms = self.get_last_sms('+99912345678')
        self.assertEqual(sms.direction, 'O')
        self.assertEqual(sms.text, 'hello')
        self.assertFalse(sms.error)
        self.assertIsNone(sms.system_error_message)

    def test_custom_opt_keywords(self):
        self.assertEqual(PhoneBlacklist.objects.count(), 0)

        self.handle_incoming('19912345678', 'join opt-test', 'TEST')
        v = PhoneNumber.get_two_way_number('19912345678')
        self.assertIsNotNone(v)

        send_sms_to_verified_number(v, 'hello')
        sms = self.get_last_sms('+19912345678')
        self.assertEqual(sms.direction, 'O')
        self.assertEqual(sms.text, 'hello')

        self.handle_incoming('19912345678', 'restop', 'TEST')
        self.assertEqual(PhoneBlacklist.objects.count(), 1)
        phone_number = PhoneBlacklist.objects.get(phone_number='19912345678')
        self.assertFalse(phone_number.send_sms)

        send_sms_to_verified_number(v, 'hello')
        sms = self.get_last_sms('+19912345678')
        self.assertEqual(sms.direction, 'O')
        self.assertEqual(sms.text, 'hello')
        self.assertTrue(sms.error)
        self.assertEqual(sms.system_error_message, SMS.ERROR_PHONE_NUMBER_OPTED_OUT)

        self.handle_incoming('19912345678', 'restart', 'TEST')
        self.assertEqual(PhoneBlacklist.objects.count(), 1)
        phone_number = PhoneBlacklist.objects.get(phone_number='19912345678')
        self.assertTrue(phone_number.send_sms)

        send_sms_to_verified_number(v, 'hello')
        sms = self.get_last_sms('+19912345678')
        self.assertEqual(sms.direction, 'O')
        self.assertEqual(sms.text, 'hello')
        self.assertFalse(sms.error)
        self.assertIsNone(sms.system_error_message)
