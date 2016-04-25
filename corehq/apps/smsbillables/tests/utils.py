class FakeTwilioMessage(object):
    status = 'sent'

    def __init__(self, price):
        self.price = price


class FakeTwilioMessageFactory(object):
    backend_message_id_to_num_segments = {}

    @classmethod
    def add_price_for_message(cls, backend_message_id, price):
        cls.backend_message_id_to_price[backend_message_id] = price

    @classmethod
    def get_price_for_message(cls, backend_message_id):
        return cls.backend_message_id_to_price.get(backend_message_id)

    @classmethod
    def get_message(cls, backend_message_id):
        return FakeTwilioMessage(
            cls.get_price_for_message(backend_message_id) * -1,
        )
