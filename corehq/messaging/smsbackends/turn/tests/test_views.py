from unittest.mock import patch
from django.test import RequestFactory, SimpleTestCase
from corehq.messaging.smsbackends.turn import views


class TurnIncomingSMSViewTests(SimpleTestCase):
    @patch.object(views, 'incoming_sms')
    def test_handles_unexpected_message_types(self, mock_incoming_sms):
        view = views.TurnIncomingSMSView()
        body = {
            'messages': [self._create_message(type='interactive')]
        }
        request = RequestFactory().post('/some/url', data=body, content_type='application/json')
        view.post(request, 'api_key')

        mock_incoming_sms.assert_called()

    def _create_message(self, id='5', from_='+111111111111', type='text'):
        return {
            'id': id,
            'from': from_,
            'type': type
        }
