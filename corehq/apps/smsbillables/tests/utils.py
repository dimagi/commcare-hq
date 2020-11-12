import uuid
from datetime import datetime

from corehq.apps.sms.models import OUTGOING, SMS
from corehq.apps.smsbillables.models import SmsGatewayFee

short_text = "This is a test text message under 160 characters."

long_text = (
    "This is a test text message that's over 160 characters in length. "
    "Or at least it will be. Thinking about kale. I like kale. Kale is "
    "a fantastic thing. Also bass music. I really like dat bass."
)


def get_fake_sms(domain, backend_api_id, backend_couch_id, text):
    msg = SMS(
        domain=domain,
        phone_number='+12223334444',
        direction=OUTGOING,
        date=datetime.utcnow(),
        backend_api=backend_api_id,
        backend_id=backend_couch_id,
        backend_message_id=uuid.uuid4().hex,
        text=text
    )
    msg.save()
    return msg


def create_gateway_fee(backend_id, message, amount, country_code=None):
    return SmsGatewayFee.create_new(backend_id, message.direction, amount,
                                    country_code=country_code)


class FakeTwilioMessage(object):
    status = 'sent'

    def __init__(self, price, num_segments=1):
        self.price = price
        self.num_segments = str(num_segments)

    def fetch(self):
        return self


class FakeMessageFactory(object):
    backend_message_id_to_num_segments = {}
    backend_message_id_to_price = {}

    @classmethod
    def add_price_for_message(cls, backend_message_id, price):
        cls.backend_message_id_to_price[backend_message_id] = price

    @classmethod
    def get_price_for_message(cls, backend_message_id):
        return cls.backend_message_id_to_price.get(backend_message_id)

    @classmethod
    def add_num_segments_for_message(cls, backend_message_id, num_segments):
        cls.backend_message_id_to_num_segments[backend_message_id] = num_segments

    @classmethod
    def get_num_segments_for_message(cls, backend_message_id):
        return cls.backend_message_id_to_num_segments.get(backend_message_id) or 1

    @classmethod
    def get_twilio_message(cls, backend_message_id):
        return FakeTwilioMessage(
            cls.get_price_for_message(backend_message_id) * -1,
            num_segments=cls.get_num_segments_for_message(backend_message_id),
        )

    @classmethod
    def get_infobip_message(cls, backend_message_id):
        return {
            'messageCount': cls.get_num_segments_for_message(backend_message_id),
            'status': {
                'name': 'sent'
            },
            'price': {
                'pricePerMessage': cls.get_price_for_message(backend_message_id)
            }
        }
