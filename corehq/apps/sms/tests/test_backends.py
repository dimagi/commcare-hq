import json
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.models import ApiUser, PERMISSION_POST_SMS
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import (send_sms, send_sms_to_verified_number,
    send_sms_with_backend, send_sms_with_backend_name)
from corehq.apps.sms.mixin import BadSMSConfigException
from corehq.apps.sms.models import (SMS, SMSLog, CommConnectCase,
    SQLMobileBackendMapping, SQLMobileBackend, MobileBackendInvitation,
    PhoneLoadBalancingMixin)
from corehq.apps.sms.tasks import handle_outgoing
from corehq.apps.sms.tests.util import BaseSMSTest
from corehq.messaging.smsbackends.apposit.models import SQLAppositBackend
from corehq.messaging.smsbackends.grapevine.models import SQLGrapevineBackend
from corehq.messaging.smsbackends.http.models import SQLHttpBackend
from corehq.messaging.smsbackends.mach.models import SQLMachBackend
from corehq.messaging.smsbackends.megamobile.models import SQLMegamobileBackend
from corehq.messaging.smsbackends.sislog.models import SQLSislogBackend
from corehq.messaging.smsbackends.smsgh.models import SQLSMSGHBackend
from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.messaging.smsbackends.tropo.models import SQLTropoBackend
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.messaging.smsbackends.unicel.models import SQLUnicelBackend, InboundParams
from corehq.messaging.smsbackends.yo.models import SQLYoBackend
from datetime import datetime
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.parsing import json_format_datetime
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from mock import patch
from urllib import urlencode


class AllBackendTest(BaseSMSTest):
    def setUp(self):
        super(AllBackendTest, self).setUp()

        self.domain_obj = Domain(name='all-backend-test')
        self.domain_obj.save()
        self.create_account_and_subscription(self.domain_obj.name)
        self.domain_obj = Domain.get(self.domain_obj._id)

        self.test_phone_number = '99912345'
        self.contact1 = CommCareCase(domain=self.domain_obj.name)
        self.contact1.set_case_property('contact_phone_number', self.test_phone_number)
        self.contact1.set_case_property('contact_phone_number_is_verified', '1')
        self.contact1.save()
        self.contact1 = CommConnectCase.wrap(self.contact1.to_json())

        # For use with megamobile only
        self.contact2 = CommCareCase(domain=self.domain_obj.name)
        self.contact2.set_case_property('contact_phone_number', '63%s' % self.test_phone_number)
        self.contact2.set_case_property('contact_phone_number_is_verified', '1')
        self.contact2.save()
        self.contact2 = CommConnectCase.wrap(self.contact2.to_json())

        self.unicel_backend = SQLUnicelBackend(
            name='UNICEL',
            is_global=True,
            hq_api_id=SQLUnicelBackend.get_api_id()
        )
        self.unicel_backend.save()

        self.mach_backend = SQLMachBackend(
            name='MACH',
            is_global=True,
            hq_api_id=SQLMachBackend.get_api_id()
        )
        self.mach_backend.save()

        self.tropo_backend = SQLTropoBackend(
            name='TROPO',
            is_global=True,
            hq_api_id=SQLTropoBackend.get_api_id()
        )
        self.tropo_backend.save()

        self.http_backend = SQLHttpBackend(
            name='HTTP',
            is_global=True,
            hq_api_id=SQLHttpBackend.get_api_id()
        )
        self.http_backend.save()

        self.telerivet_backend = SQLTelerivetBackend(
            name='TELERIVET',
            is_global=True,
            hq_api_id=SQLTelerivetBackend.get_api_id()
        )
        self.telerivet_backend.set_extra_fields(
            **dict(
                webhook_secret='telerivet-webhook-secret'
            )
        )
        self.telerivet_backend.save()

        self.test_backend = SQLTestSMSBackend(
            name='TEST',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        self.test_backend.save()

        self.grapevine_backend = SQLGrapevineBackend(
            name='GRAPEVINE',
            is_global=True,
            hq_api_id=SQLGrapevineBackend.get_api_id()
        )
        self.grapevine_backend.save()

        self.twilio_backend = SQLTwilioBackend(
            name='TWILIO',
            is_global=True,
            hq_api_id=SQLTwilioBackend.get_api_id()
        )
        self.twilio_backend.save()

        self.megamobile_backend = SQLMegamobileBackend(
            name='MEGAMOBILE',
            is_global=True,
            hq_api_id=SQLMegamobileBackend.get_api_id()
        )
        self.megamobile_backend.save()

        self.smsgh_backend = SQLSMSGHBackend(
            name='SMSGH',
            is_global=True,
            hq_api_id=SQLSMSGHBackend.get_api_id()
        )
        self.smsgh_backend.save()

        self.apposit_backend = SQLAppositBackend(
            name='APPOSIT',
            is_global=True,
            hq_api_id=SQLAppositBackend.get_api_id()
        )
        self.apposit_backend.save()

        self.sislog_backend = SQLSislogBackend(
            name='SISLOG',
            is_global=True,
            hq_api_id=SQLSislogBackend.get_api_id()
        )
        self.sislog_backend.save()

        self.yo_backend = SQLYoBackend(
            name='YO',
            is_global=True,
            hq_api_id=SQLYoBackend.get_api_id()
        )
        self.yo_backend.save()

    def _test_outbound_backend(self, backend, msg_text, mock_send):
        SQLMobileBackendMapping.set_default_domain_backend(self.domain_obj.name, backend)

        send_sms(self.domain_obj.name, None, self.test_phone_number, msg_text)
        sms = SMS.objects.get(
            domain=self.domain_obj.name,
            direction='O',
            text=msg_text
        )

        self.assertTrue(mock_send.called)
        msg_arg = mock_send.call_args[0][0]
        self.assertEqual(msg_arg.date, sms.date)
        self.assertEqual(sms.backend_api, backend.hq_api_id)
        self.assertEqual(sms.backend_id, backend.couch_id)

    def _verify_inbound_request(self, backend_api_id, msg_text):
        sms = SMS.objects.get(
            domain=self.domain_obj.name,
            direction='I',
            text=msg_text
        )
        self.assertEqual(sms.backend_api, backend_api_id)

    def _simulate_inbound_request_with_payload(self, url,
            content_type, payload):
        response = Client().post(url, payload, content_type=content_type)
        self.assertEqual(response.status_code, 200)

    def _simulate_inbound_request(self, url, phone_param,
            msg_param, msg_text, post=False, additional_params=None):
        fcn = Client().post if post else Client().get

        payload = {
            phone_param: self.test_phone_number,
            msg_param: msg_text,
        }

        if additional_params:
            payload.update(additional_params)

        response = fcn(url, payload)
        self.assertEqual(response.status_code, 200)

    @patch('corehq.messaging.smsbackends.unicel.models.SQLUnicelBackend.send')
    @patch('corehq.messaging.smsbackends.mach.models.SQLMachBackend.send')
    @patch('corehq.messaging.smsbackends.tropo.models.SQLTropoBackend.send')
    @patch('corehq.messaging.smsbackends.http.models.SQLHttpBackend.send')
    @patch('corehq.messaging.smsbackends.telerivet.models.SQLTelerivetBackend.send')
    @patch('corehq.messaging.smsbackends.test.models.SQLTestSMSBackend.send')
    @patch('corehq.messaging.smsbackends.grapevine.models.SQLGrapevineBackend.send')
    @patch('corehq.messaging.smsbackends.twilio.models.SQLTwilioBackend.send')
    @patch('corehq.messaging.smsbackends.megamobile.models.SQLMegamobileBackend.send')
    @patch('corehq.messaging.smsbackends.smsgh.models.SQLSMSGHBackend.send')
    @patch('corehq.messaging.smsbackends.apposit.models.SQLAppositBackend.send')
    @patch('corehq.messaging.smsbackends.sislog.models.SQLSislogBackend.send')
    @patch('corehq.messaging.smsbackends.yo.models.SQLYoBackend.send')
    def test_outbound_sms(
            self,
            yo_send,
            sislog_send,
            apposit_send,
            smsgh_send,
            megamobile_send,
            twilio_send,
            grapevine_send,
            test_send,
            telerivet_send,
            http_send,
            tropo_send,
            mach_send,
            unicel_send):
        self._test_outbound_backend(self.unicel_backend, 'unicel test', unicel_send)
        self._test_outbound_backend(self.mach_backend, 'mach test', mach_send)
        self._test_outbound_backend(self.tropo_backend, 'tropo test', tropo_send)
        self._test_outbound_backend(self.http_backend, 'http test', http_send)
        self._test_outbound_backend(self.telerivet_backend, 'telerivet test', telerivet_send)
        self._test_outbound_backend(self.test_backend, 'test test', test_send)
        self._test_outbound_backend(self.grapevine_backend, 'grapevine test', grapevine_send)
        self._test_outbound_backend(self.twilio_backend, 'twilio test', twilio_send)
        self._test_outbound_backend(self.megamobile_backend, 'megamobile test', megamobile_send)
        self._test_outbound_backend(self.smsgh_backend, 'smsgh test', smsgh_send)
        self._test_outbound_backend(self.apposit_backend, 'apposit test', apposit_send)
        self._test_outbound_backend(self.sislog_backend, 'sislog test', sislog_send)
        self._test_outbound_backend(self.yo_backend, 'yo test', yo_send)

    def test_unicel_inbound_sms(self):
        self._simulate_inbound_request('/unicel/in/', phone_param=InboundParams.SENDER,
            msg_param=InboundParams.MESSAGE, msg_text='unicel test')

        self._verify_inbound_request(self.unicel_backend.get_api_id(), 'unicel test')

    def test_tropo_inbound_sms(self):
        tropo_data = {'session': {'from': {'id': self.test_phone_number}, 'initialText': 'tropo test'}}
        self._simulate_inbound_request_with_payload('/tropo/sms/',
            content_type='text/json', payload=json.dumps(tropo_data))

        self._verify_inbound_request(self.tropo_backend.get_api_id(), 'tropo test')

    def test_telerivet_inbound_sms(self):
        additional_params = {
            'event': 'incoming_message',
            'message_type': 'sms',
            'secret': self.telerivet_backend.config.webhook_secret
        }
        self._simulate_inbound_request('/telerivet/in/', phone_param='from_number_e164',
            msg_param='content', msg_text='telerivet test', post=True,
            additional_params=additional_params)

        self._verify_inbound_request(self.telerivet_backend.get_api_id(), 'telerivet test')

    @override_settings(SIMPLE_API_KEYS={'grapevine-test': 'grapevine-api-key'})
    def test_grapevine_inbound_sms(self):
        xml = """
        <gviSms>
            <smsDateTime>2015-10-12T12:00:00</smsDateTime>
            <cellNumber>99912345</cellNumber>
            <content>grapevine test</content>
        </gviSms>
        """
        payload = urlencode({'XML': xml})
        self._simulate_inbound_request_with_payload(
            '/gvi/api/sms/?apiuser=grapevine-test&apikey=grapevine-api-key',
            content_type='application/x-www-form-urlencoded', payload=payload)

        self._verify_inbound_request(self.grapevine_backend.get_api_id(), 'grapevine test')

    def test_twilio_inbound_sms(self):
        self._simulate_inbound_request('/twilio/sms/', phone_param='From',
            msg_param='Body', msg_text='twilio test', post=True)

        self._verify_inbound_request(self.twilio_backend.get_api_id(), 'twilio test')

    def test_megamobile_inbound_sms(self):
        self._simulate_inbound_request('/megamobile/sms/', phone_param='cel',
            msg_param='msg', msg_text='megamobile test')

        self._verify_inbound_request(self.megamobile_backend.get_api_id(), 'megamobile test')

    def test_sislog_inbound_sms(self):
        self._simulate_inbound_request('/sislog/in/', phone_param='sender',
            msg_param='msgdata', msg_text='sislog test')

        self._verify_inbound_request(self.sislog_backend.get_api_id(), 'sislog test')

    def test_yo_inbound_sms(self):
        self._simulate_inbound_request('/yo/sms/', phone_param='sender',
            msg_param='message', msg_text='yo test')

        self._verify_inbound_request(self.yo_backend.get_api_id(), 'yo test')

    def test_smsgh_inbound_sms(self):
        user = ApiUser.create('smsgh-api-key', 'smsgh-api-key', permissions=[PERMISSION_POST_SMS])
        user.save()

        self._simulate_inbound_request('/smsgh/sms/smsgh-api-key/', phone_param='snr',
            msg_param='msg', msg_text='smsgh test')

        self._verify_inbound_request('SMSGH', 'smsgh test')

        user.delete()

    def test_apposit_inbound_sms(self):
        user = ApiUser.create('apposit-api-key', 'apposit-api-key', permissions=[PERMISSION_POST_SMS])
        user.save()

        self._simulate_inbound_request(
            '/apposit/in/apposit-api-key/',
            phone_param='fromAddress',
            msg_param='content',
            msg_text='apposit test',
            post=True,
            additional_params={'channel': 'SMS'}
        )
        self._verify_inbound_request('APPOSIT', 'apposit test')

        user.delete()

    def tearDown(self):
        self.contact1.get_verified_number().delete()
        self.contact1.delete()
        self.contact2.get_verified_number().delete()
        self.contact2.delete()
        self.domain_obj.delete()
        self.unicel_backend.delete()
        self.mach_backend.delete()
        self.tropo_backend.delete()
        self.http_backend.delete()
        self.telerivet_backend.delete()
        self.test_backend.delete()
        self.grapevine_backend.delete()
        self.twilio_backend.delete()
        self.megamobile_backend.delete()
        self.smsgh_backend.delete()
        self.apposit_backend.delete()
        self.sislog_backend.delete()
        self.yo_backend.delete()
        super(AllBackendTest, self).tearDown()


class OutgoingFrameworkTestCase(BaseSMSTest):

    def setUp(self):
        super(OutgoingFrameworkTestCase, self).setUp()

        self.domain = "test-domain"
        self.domain2 = "test-domain2"

        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

        self.create_account_and_subscription(self.domain_obj.name)
        self.domain_obj = Domain.get(self.domain_obj._id)

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

        super(OutgoingFrameworkTestCase, self).tearDown()

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

    def test_choosing_appropriate_backend_for_outgoing(self):
        self.__test_global_backend_map()
        self.__test_domain_default()
        self.__test_shared_backend()
        self.__test_verified_number_with_map()
        self.__test_contact_level_backend()
        self.__test_send_sms_with_backend()
        self.__test_send_sms_with_backend_name()


class SQLMobileBackendTestCase(TestCase):
    def test_domain_is_shared(self):
        backend = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            domain='shared-test-1',
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        self.assertFalse(backend.domain_is_shared('shared-test-2'))

        backend.set_shared_domains(['shared-test-2'])
        self.assertTrue(backend.domain_is_shared('shared-test-2'))

        backend.soft_delete()
        self.assertFalse(backend.domain_is_shared('shared-test-2'))

        backend.delete()

    def test_domain_is_authorized(self):
        backend1 = SQLTestSMSBackend.objects.create(
            name='BACKEND1',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        backend2 = SQLTestSMSBackend.objects.create(
            name='BACKEND2',
            domain='auth-test-1',
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        self.assertTrue(backend1.domain_is_authorized('auth-test-1'))
        self.assertTrue(backend1.domain_is_authorized('auth-test-2'))
        self.assertTrue(backend1.domain_is_authorized('auth-test-3'))

        self.assertTrue(backend2.domain_is_authorized('auth-test-1'))
        self.assertFalse(backend2.domain_is_authorized('auth-test-2'))
        self.assertFalse(backend2.domain_is_authorized('auth-test-3'))

        backend2.set_shared_domains(['auth-test-2'])
        self.assertTrue(backend2.domain_is_authorized('auth-test-1'))
        self.assertTrue(backend2.domain_is_authorized('auth-test-2'))
        self.assertFalse(backend2.domain_is_authorized('auth-test-3'))

        backend1.delete()
        backend2.delete()

    def test_load_default_by_phone_and_domain(self):
        backend1 = SQLTestSMSBackend.objects.create(
            name='BACKEND1',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        backend2 = SQLTestSMSBackend.objects.create(
            name='BACKEND2',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        backend3 = SQLTestSMSBackend.objects.create(
            name='BACKEND3',
            is_global=False,
            domain='load-default-test',
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        backend4 = SQLTestSMSBackend.objects.create(
            name='BACKEND4',
            is_global=False,
            domain='load-default-test',
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        backend_mapping1 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='*',
            backend=backend1
        )

        backend_mapping2 = SQLMobileBackendMapping.objects.create(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            prefix='27',
            backend=backend2
        )

        backend_mapping3 = SQLMobileBackendMapping.objects.create(
            is_global=False,
            domain='load-default-test',
            backend_type=SQLMobileBackend.SMS,
            prefix='*',
            backend=backend3
        )

        backend_mapping4 = SQLMobileBackendMapping.objects.create(
            is_global=False,
            domain='load-default-test',
            backend_type=SQLMobileBackend.SMS,
            prefix='27',
            backend=backend4
        )

        # Test global prefix map
        self.assertEqual(
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '2700000000',
                domain='load-default-test-2'
            ),
            backend2
        )

        # Test domain-level prefix map
        self.assertEqual(
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '2700000000',
                domain='load-default-test'
            ),
            backend4
        )

        # Test domain catch-all
        backend4.soft_delete()
        self.assertEqual(
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '2700000000',
                domain='load-default-test'
            ),
            backend3
        )

        # Test global prefix map
        backend3.soft_delete()
        self.assertEqual(
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '2700000000',
                domain='load-default-test'
            ),
            backend2
        )

        # Test global catch-all
        backend2.soft_delete()
        self.assertEqual(
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '2700000000',
                domain='load-default-test'
            ),
            backend1
        )

        # Test raising exception if nothing found
        backend1.soft_delete()
        with self.assertRaises(BadSMSConfigException):
            SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                '2700000000',
                domain='load-default-test'
            )

        backend1.delete()
        backend2.delete()
        backend3.delete()
        backend4.delete()

    def test_get_backend_api_id(self):
        backend = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        self.assertEquals(
            SQLMobileBackend.get_backend_api_id(backend.pk),
            SQLTestSMSBackend.get_api_id()
        )

        self.assertEquals(
            SQLMobileBackend.get_backend_api_id(backend.couch_id, is_couch_id=True),
            SQLTestSMSBackend.get_api_id()
        )

        backend.soft_delete()
        with self.assertRaises(SQLMobileBackend.DoesNotExist):
            SQLMobileBackend.get_backend_api_id(backend.pk)

        with self.assertRaises(SQLMobileBackend.DoesNotExist):
            SQLMobileBackend.get_backend_api_id(backend.couch_id, is_couch_id=True)

        backend.delete()

    def test_load(self):
        backend = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        self.assertEquals(
            SQLMobileBackend.load(backend.pk),
            backend
        )

        self.assertEquals(
            SQLMobileBackend.load(backend.pk, api_id=SQLTestSMSBackend.get_api_id()),
            backend
        )

        self.assertEquals(
            SQLMobileBackend.load(backend.couch_id, is_couch_id=True),
            backend
        )

        self.assertEquals(
            SQLMobileBackend.load(
                backend.couch_id,
                api_id=SQLTestSMSBackend.get_api_id(),
                is_couch_id=True
            ),
            backend
        )

        backend.soft_delete()

        with self.assertRaises(SQLMobileBackend.DoesNotExist):
            SQLMobileBackend.load(backend.pk, api_id=SQLTestSMSBackend.get_api_id())

        with self.assertRaises(SQLMobileBackend.DoesNotExist):
            SQLMobileBackend.load(
                backend.couch_id,
                api_id=SQLTestSMSBackend.get_api_id(),
                is_couch_id=True
            )

        with self.assertRaises(BadSMSConfigException):
            SQLMobileBackend.load(backend.pk, api_id='this-api-id-does-not-exist')

        backend.delete()

    def test_load_by_name(self):
        backend1 = SQLTestSMSBackend.objects.create(
            name='BACKEND_BY_NAME_TEST',
            is_global=False,
            domain='backend-by-name-test-1',
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        backend2 = SQLTestSMSBackend.objects.create(
            name='BACKEND_BY_NAME_TEST',
            is_global=False,
            domain='backend-by-name-test-2',
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )
        backend2.set_shared_domains(['backend-by-name-test-1'])

        backend3 = SQLTestSMSBackend.objects.create(
            name='BACKEND_BY_NAME_TEST',
            is_global=True,
            hq_api_id=SQLTestSMSBackend.get_api_id(),
        )

        self.assertEqual(
            SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                'backend-by-name-test-1',
                'BACKEND_BY_NAME_TEST'
            ),
            backend1
        )

        self.assertEqual(
            SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                'backend-by-name-test-3',
                'BACKEND_BY_NAME_TEST'
            ),
            backend3
        )

        backend1.soft_delete()
        self.assertEqual(
            SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                'backend-by-name-test-1',
                'BACKEND_BY_NAME_TEST'
            ),
            backend2
        )

        backend2.set_shared_domains([])
        self.assertEqual(
            SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                'backend-by-name-test-1',
                'BACKEND_BY_NAME_TEST'
            ),
            backend3
        )

        self.assertEqual(
            SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                'backend-by-name-test-2',
                'BACKEND_BY_NAME_TEST'
            ),
            backend2
        )

        backend2.soft_delete()
        self.assertEqual(
            SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                'backend-by-name-test-2',
                'BACKEND_BY_NAME_TEST'
            ),
            backend3
        )

        backend3.soft_delete()
        with self.assertRaises(BadSMSConfigException):
            SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                'backend-by-name-test-1',
                'BACKEND_BY_NAME_TEST'
            )

        backend1.delete()
        backend2.delete()
        backend3.delete()


class LoadBalanceBackend(SQLTestSMSBackend, PhoneLoadBalancingMixin):
    class Meta:
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'LOAD_BALANCE'


class RateLimitBackend(SQLTestSMSBackend):
    class Meta:
        proxy = True

    def get_sms_rate_limit(self):
        return 10

    @classmethod
    def get_api_id(cls):
        return 'RATE_LIMIT'


class LoadBalanceAndRateLimitBackend(SQLTestSMSBackend, PhoneLoadBalancingMixin):
    class Meta:
        proxy = True

    def get_sms_rate_limit(self):
        return 10


    @classmethod
    def get_api_id(cls):
        return 'LOAD_BALANCE_RATE_LIMIT'


def mock_get_backend_classes():
    return {
        LoadBalanceBackend.get_api_id(): LoadBalanceBackend,
        RateLimitBackend.get_api_id(): RateLimitBackend,
        LoadBalanceAndRateLimitBackend.get_api_id(): LoadBalanceAndRateLimitBackend,
    }


@patch('corehq.apps.sms.util.get_backend_classes', new=mock_get_backend_classes)
class LoadBalancingAndRateLimitingTestCase(BaseSMSTest):
    def setUp(self):
        super(LoadBalancingAndRateLimitingTestCase, self).setUp()
        self.domain = 'load-balance-rate-limit'
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()
        self.create_account_and_subscription(self.domain)
        self.domain_obj = Domain.get(self.domain_obj.get_id)

    def tearDown(self):
        self.domain_obj.delete()
        super(LoadBalancingAndRateLimitingTestCase, self).tearDown()

    def create_outgoing_sms(self, backend):
        sms = SMSLog(
            domain=self.domain,
            date=datetime.utcnow(),
            direction='O',
            phone_number='9991234567',
            text='message',
            backend_id=backend.couch_id
        )
        sms.save()
        return sms

    def delete_load_balancing_keys(self, backend):
        # This should only be necessary when running tests locally, but doesn't
        # hurt to run all the time.
        client = get_redis_client().client.get_client()
        client.delete(backend.get_load_balance_redis_key())

    def assertRequeue(self, backend):
        requeue_flag = handle_outgoing(self.create_outgoing_sms(backend))
        self.assertTrue(requeue_flag)

    def assertNotRequeue(self, backend):
        requeue_flag = handle_outgoing(self.create_outgoing_sms(backend))
        self.assertFalse(requeue_flag)

    def test_load_balance(self):
        backend = LoadBalanceBackend.objects.create(
            name='BACKEND',
            is_global=True,
            load_balancing_numbers=['9990001', '9990002', '9990003'],
            hq_api_id=LoadBalanceBackend.get_api_id()
        )
        self.delete_load_balancing_keys(backend)

        for i in range(5):
            with patch('corehq.apps.sms.tests.LoadBalanceBackend.send') as mock_send:
                self.assertNotRequeue(backend)
                self.assertTrue(mock_send.called)
                self.assertEqual(mock_send.call_args[1]['orig_phone_number'], '9990001')

                self.assertNotRequeue(backend)
                self.assertTrue(mock_send.called)
                self.assertEqual(mock_send.call_args[1]['orig_phone_number'], '9990002')

                self.assertNotRequeue(backend)
                self.assertTrue(mock_send.called)
                self.assertEqual(mock_send.call_args[1]['orig_phone_number'], '9990003')

        backend.delete()

    def test_rate_limit(self):
        backend = RateLimitBackend.objects.create(
            name='BACKEND',
            is_global=True,
            hq_api_id=RateLimitBackend.get_api_id()
        )

        # Requeue flag should be False until we hit the limit
        for i in range(backend.get_sms_rate_limit()):
            with patch('corehq.apps.sms.tests.RateLimitBackend.send') as mock_send:
                self.assertNotRequeue(backend)
                self.assertTrue(mock_send.called)

        # Requeue flag should be True after hitting the limit
        with patch('corehq.apps.sms.tests.RateLimitBackend.send') as mock_send:
            self.assertRequeue(backend)
            self.assertFalse(mock_send.called)

        backend.delete()

    def test_load_balance_and_rate_limit(self):
        backend = LoadBalanceAndRateLimitBackend.objects.create(
            name='BACKEND',
            is_global=True,
            load_balancing_numbers=['9990001', '9990002', '9990003'],
            hq_api_id=LoadBalanceAndRateLimitBackend.get_api_id()
        )
        self.delete_load_balancing_keys(backend)

        for i in range(backend.get_sms_rate_limit()):
            with patch('corehq.apps.sms.tests.LoadBalanceAndRateLimitBackend.send') as mock_send:
                self.assertNotRequeue(backend)
                self.assertTrue(mock_send.called)
                self.assertEqual(mock_send.call_args[1]['orig_phone_number'], '9990001')

                self.assertNotRequeue(backend)
                self.assertTrue(mock_send.called)
                self.assertEqual(mock_send.call_args[1]['orig_phone_number'], '9990002')

                self.assertNotRequeue(backend)
                self.assertTrue(mock_send.called)
                self.assertEqual(mock_send.call_args[1]['orig_phone_number'], '9990003')

        with patch('corehq.apps.sms.tests.LoadBalanceAndRateLimitBackend.send') as mock_send:
            self.assertRequeue(backend)
            self.assertFalse(mock_send.called)

            self.assertRequeue(backend)
            self.assertFalse(mock_send.called)

            self.assertRequeue(backend)
            self.assertFalse(mock_send.called)

        backend.delete()
