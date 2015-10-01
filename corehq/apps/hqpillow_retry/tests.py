import datetime
from django.test import TestCase
from corehq.apps.hqpillow_retry.management.commands.run_pillow_retry_queue import \
    PillowRetryEnqueuingOperation


class PillowRetryEnqueuingOperationTest(TestCase):
    def test_get_items_to_be_processed(self):
        # just assert this doesn't error
        PillowRetryEnqueuingOperation.get_items_to_be_processed(datetime.datetime.utcnow())
