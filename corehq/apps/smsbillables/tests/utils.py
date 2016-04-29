class FakeTwilioMessage(object):
    status = 'sent'

    def __init__(self, price, num_segments=1):
        self.price = price
        self.num_segments = unicode(num_segments)


class FakeTwilioMessageFactory(object):
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
    def get_message(cls, backend_message_id):
        return FakeTwilioMessage(
            cls.get_price_for_message(backend_message_id) * -1,
            num_segments=cls.get_num_segments_for_message(backend_message_id),
        )
