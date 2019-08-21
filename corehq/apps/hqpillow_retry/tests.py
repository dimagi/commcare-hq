from __future__ import absolute_import
import datetime
from django.test import TestCase
from pillow_retry.models import PillowError
from corehq.apps.hqpillow_retry.management.commands.run_pillow_retry_queue import \
    PillowRetryEnqueuingOperation


class PillowRetryEnqueuingOperationTest(TestCase):

    def test_get_items_to_be_processed(self):
        p = PillowError(
            date_created=datetime.datetime.utcnow() - datetime.timedelta(days=1),
            date_next_attempt=datetime.datetime.utcnow() - datetime.timedelta(days=2),
            date_last_attempt=datetime.datetime.utcnow() - datetime.timedelta(days=3),
        )
        p.save()
        self.addCleanup(p.delete)
        errors = list(PillowRetryEnqueuingOperation().get_items_to_be_processed(
            datetime.datetime.utcnow()))
        self.assertTrue(errors)
