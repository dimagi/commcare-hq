import uuid
from datetime import datetime

from django.apps import apps
from django.conf import settings

from corehq.apps.sms.models import SMS

short_text = "This is a test text message under 160 characters."

long_text = (
    "This is a test text message that's over 160 characters in length. "
    "Or at least it will be. Thinking about kale. I like kale. Kale is "
    "a fantastic thing. Also bass music. I really like dat bass."
)


def bootstrap_smsbillables():
    from ..management.commands.add_moz_zero_charge import add_moz_zero_charge
    from ..management.commands.bootstrap_grapevine_gateway import bootstrap_grapevine_gateway
    from ..management.commands.bootstrap_grapevine_gateway_update import bootstrap_grapevine_gateway_update
    from ..management.commands.bootstrap_mach_gateway import bootstrap_mach_gateway
    from ..management.commands.bootstrap_moz_gateway import bootstrap_moz_gateway
    from ..management.commands.bootstrap_telerivet_gateway import bootstrap_telerivet_gateway
    from ..management.commands.bootstrap_test_gateway import bootstrap_test_gateway
    from ..management.commands.bootstrap_tropo_gateway import bootstrap_tropo_gateway
    from ..management.commands.bootstrap_usage_fees import bootstrap_usage_fees
    from ..management.commands.bootstrap_yo_gateway import bootstrap_yo_gateway

    Currency = apps.get_model("accounting", "Currency")
    Currency.objects.get_or_create(code=settings.DEFAULT_CURRENCY)
    Currency.objects.get_or_create(code='EUR')
    Currency.objects.get_or_create(code='INR')

    bootstrap_grapevine_gateway(apps)
    bootstrap_mach_gateway(apps)
    bootstrap_tropo_gateway(apps)
    bootstrap_usage_fees(apps)
    bootstrap_moz_gateway(apps)
    bootstrap_test_gateway(apps)
    bootstrap_telerivet_gateway(apps)
    bootstrap_yo_gateway(apps)
    add_moz_zero_charge(apps)
    bootstrap_grapevine_gateway_update(apps)


def create_sms(domain, backend, number, direction, text):
    msg = SMS(
        domain=domain,
        phone_number=number,
        direction=direction,
        date=datetime.utcnow(),
        backend_api=backend.hq_api_id,
        backend_id=backend.couch_id,
        backend_message_id=uuid.uuid4().hex,
        text=text
    )
    msg.save()
    return msg


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
