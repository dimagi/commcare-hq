from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.airtel_tcl.exceptions import AirtelTCLError, InvalidDestinationNumber
from corehq.messaging.smsbackends.airtel_tcl.models import AirtelTCLBackend
from datetime import datetime
from django.test import TestCase
from mock import patch


class AirtelTCLBackendTest(TestCase):

    def unicode_to_decimal_ncr(self):
        self.assertEqual(
            AirtelTCLBackend.unicode_to_decimal_ncr(
                '\u0928\u092e\u0938\u094d\u0924\u0947 \u0928\u092e\u0938\u094d\u0924\u0947'
            ),
            '&#2344;&#2350;&#2360;&#2381;&#2340;&#2375;&#32;&#2344;&#2350;&#2360;&#2381;&#2340;&#2375;'
        )

    def test_get_text_and_lang_id(self):
        self.assertEqual(
            AirtelTCLBackend.get_text_and_lang_id(QueuedSMS(text='abc')),
            ('abc', None)
        )
        self.assertEqual(
            AirtelTCLBackend.get_text_and_lang_id(QueuedSMS(text='\u0928\u092e\u0938\u094d\u0924\u0947')),
            ('&#2344;&#2350;&#2360;&#2381;&#2340;&#2375;', '2')
        )

    def test_get_formatted_timestamp(self):
        self.assertEqual(
            AirtelTCLBackend.get_formatted_timestamp(datetime(2018, 9, 7, 12, 34, 56)),
            '07092018123456'
        )

    @patch('corehq.messaging.smsbackends.airtel_tcl.models.AirtelTCLBackend.get_timestamp')
    def test_get_json_payload_unicode(self, get_timestamp_mock):
        get_timestamp_mock.return_value = datetime(2018, 9, 7, 12, 34, 56)

        backend = AirtelTCLBackend()
        backend.set_extra_fields(
            user_name='abc',
            sender_id='def',
            circle_name='ghi',
            campaign_name='jkl',
        )

        msg_obj = QueuedSMS(text='\u0928\u092e\u0938\u094d\u0924\u0947', phone_number='+910123456789')
        payload = backend.get_json_payload(msg_obj)
        self.assertEqual(
            payload,
            {
                'timeStamp': '07092018123456',
                'keyword': 'ICDS',
                'dataSet': [
                    {
                        'MSISDN': '0123456789',
                        'OA': 'def',
                        'CIRCLE_NAME': 'ghi',
                        'CAMPAIGN_NAME': 'jkl',
                        'MESSAGE': '&#2344;&#2350;&#2360;&#2381;&#2340;&#2375;',
                        'USER_NAME': 'abc',
                        'CHANNEL': 'SMS',
                        'LANG_ID': '2',
                    }
                ],
            }
        )

    @patch('corehq.messaging.smsbackends.airtel_tcl.models.AirtelTCLBackend.get_timestamp')
    def test_get_json_payload_ascii(self, get_timestamp_mock):
        get_timestamp_mock.return_value = datetime(2018, 9, 7, 12, 34, 56)

        backend = AirtelTCLBackend()
        backend.set_extra_fields(
            user_name='abc',
            sender_id='def',
            circle_name='ghi',
            campaign_name='jkl',
        )

        msg_obj = QueuedSMS(text='message', phone_number='+910123456789')
        payload = backend.get_json_payload(msg_obj)
        self.assertEqual(
            payload,
            {
                'timeStamp': '07092018123456',
                'keyword': 'ICDS',
                'dataSet': [
                    {
                        'MSISDN': '0123456789',
                        'OA': 'def',
                        'CIRCLE_NAME': 'ghi',
                        'CAMPAIGN_NAME': 'jkl',
                        'MESSAGE': 'message',
                        'USER_NAME': 'abc',
                        'CHANNEL': 'SMS',
                    }
                ],
            }
        )

    def test_get_url(self):
        backend = AirtelTCLBackend()
        backend.set_extra_fields(
            host_and_port='localhost:8000',
        )
        self.assertEqual(
            backend.get_url(),
            'https://localhost:8000/BULK_API/InstantJsonPush'
        )

    def test_get_phone_number(self):
        self.assertEqual(AirtelTCLBackend.get_phone_number('+910123456789'), '0123456789')
        self.assertEqual(AirtelTCLBackend.get_phone_number('910123456789'), '0123456789')

        with self.assertRaises(InvalidDestinationNumber):
            AirtelTCLBackend.get_phone_number('+999123456')

        with self.assertRaises(InvalidDestinationNumber):
            AirtelTCLBackend.get_phone_number('+91')

    def test_handle_response(self):
        with self.assertRaises(AirtelTCLError):
            AirtelTCLBackend.handle_response(500, 'true')

        with self.assertRaises(AirtelTCLError):
            AirtelTCLBackend.handle_response(200, 'false')

        # No exception raised
        AirtelTCLBackend.handle_response(200, 'true')
