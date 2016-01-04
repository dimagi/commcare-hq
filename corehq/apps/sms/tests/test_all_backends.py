import json
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.models import ApiUser, PERMISSION_POST_SMS
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms
from corehq.apps.sms.models import SMS, CommConnectCase
from corehq.apps.sms import mixin as backend_api
from corehq.apps.sms.tests.util import BaseSMSTest
from corehq.messaging.smsbackends.unicel.models import UnicelBackend, InboundParams
from corehq.messaging.smsbackends.mach.models import MachBackend
from corehq.messaging.smsbackends.tropo.models import TropoBackend
from corehq.messaging.smsbackends.http.models import HttpBackend
from corehq.messaging.smsbackends.telerivet.models import TelerivetBackend
from corehq.messaging.smsbackends.test.models import TestSMSBackend
from corehq.messaging.smsbackends.grapevine.models import GrapevineBackend
from corehq.messaging.smsbackends.twilio.models import TwilioBackend
from corehq.messaging.smsbackends.megamobile.models import MegamobileBackend
from corehq.messaging.smsbackends.smsgh.models import SMSGHBackend
from corehq.messaging.smsbackends.apposit.models import AppositBackend
from dimagi.utils.parsing import json_format_datetime
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from mock import patch
from urllib import urlencode


class AllBackendTest(BaseSMSTest):
    def setUp(self):
        super(AllBackendTest, self).setUp()
        backend_api.TEST = True

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

        self.unicel_backend = UnicelBackend(name='UNICEL', is_global=True)
        self.unicel_backend.save()

        self.mach_backend = MachBackend(name='MACH', is_global=True)
        self.mach_backend.save()

        self.tropo_backend = TropoBackend(name='TROPO', is_global=True)
        self.tropo_backend.save()

        self.http_backend = HttpBackend(name='HTTP', is_global=True)
        self.http_backend.save()

        self.telerivet_backend = TelerivetBackend(name='TELERIVET', is_global=True,
            webhook_secret='telerivet-webhook-secret')
        self.telerivet_backend.save()

        self.test_backend = TestSMSBackend(name='TEST', is_global=True)
        self.test_backend.save()

        self.grapevine_backend = GrapevineBackend(name='GRAPEVINE', is_global=True)
        self.grapevine_backend.save()

        self.twilio_backend = TwilioBackend(name='TWILIO', is_global=True)
        self.twilio_backend.save()

        self.megamobile_backend = MegamobileBackend(name='MEGAMOBILE', is_global=True)
        self.megamobile_backend.save()

        self.smsgh_backend = SMSGHBackend(name='SMSGH', is_global=True)
        self.smsgh_backend.save()

        self.apposit_backend = AppositBackend(name='APPOSIT', is_global=True)
        self.apposit_backend.save()

    def _test_outbound_backend(self, backend, msg_text, mock_send):
        self.domain_obj.default_sms_backend_id = backend._id
        self.domain_obj.save()

        send_sms(self.domain_obj.name, None, self.test_phone_number, msg_text)
        sms = SMS.objects.get(
            domain=self.domain_obj.name,
            direction='O',
            text=msg_text
        )

        self.assertTrue(mock_send.called)
        msg_arg = mock_send.call_args[0][0]
        self.assertEqual(msg_arg.date, sms.date)

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

    @patch('corehq.messaging.smsbackends.unicel.models.UnicelBackend.send')
    @patch('corehq.messaging.smsbackends.mach.models.MachBackend.send')
    @patch('corehq.messaging.smsbackends.tropo.models.TropoBackend.send')
    @patch('corehq.messaging.smsbackends.http.models.HttpBackend.send')
    @patch('corehq.messaging.smsbackends.telerivet.models.TelerivetBackend.send')
    @patch('corehq.messaging.smsbackends.test.models.TestSMSBackend.send')
    @patch('corehq.messaging.smsbackends.grapevine.models.GrapevineBackend.send')
    @patch('corehq.messaging.smsbackends.twilio.models.TwilioBackend.send')
    @patch('corehq.messaging.smsbackends.megamobile.models.MegamobileBackend.send')
    @patch('corehq.messaging.smsbackends.smsgh.models.SMSGHBackend.send')
    @patch('corehq.messaging.smsbackends.apposit.models.AppositBackend.send')
    def test_outbound_sms(
            self,
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
            'secret': self.telerivet_backend.webhook_secret
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

        self._verify_inbound_request('SISLOG', 'sislog test')

    def test_yo_inbound_sms(self):
        self._simulate_inbound_request('/yo/sms/', phone_param='sender',
            msg_param='message', msg_text='yo test')

        self._verify_inbound_request('YO', 'yo test')

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
        backend_api.TEST = False
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
        super(AllBackendTest, self).tearDown()
