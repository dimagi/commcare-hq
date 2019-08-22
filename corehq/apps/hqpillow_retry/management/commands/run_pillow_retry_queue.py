from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime
from time import sleep

import pytz
from django import db
from django.core.management import BaseCommand
from psycopg2._psycopg import InterfaceError

from corehq.apps.change_feed.producer import ChangeProducer
from corehq.sql_db.util import handle_connection_failure
from dimagi.utils.logging import notify_exception
from pillow_retry.api import process_pillow_retry
from pillow_retry.models import PillowError

BATCH_SIZE = 10000

producer = ChangeProducer(auto_flush=False)


class PillowRetryEnqueuingOperation(BaseCommand):
    help = "Runs the Pillow Retry Queue"

    def handle(self, **options):
        while True:
            try:
                num_processed = self.process_queue()
            except Exception:
                num_processed = 0
                notify_exception(None, message="Could not fetch due survey actions")
            sleep_time = 10 if num_processed < BATCH_SIZE else 0
            sleep(sleep_time)

    @handle_connection_failure()
    def process_queue(self):
        utcnow = datetime.utcnow()
        errors = self.get_items_to_be_processed(utcnow)
        for error in errors:
            process_pillow_retry(error, producer=producer)
        producer.flush()
        return len(errors)

    def get_items_to_be_processed(self, utcnow):
        # We're just querying for ids here, so no need to limit
        utcnow = utcnow.replace(tzinfo=pytz.UTC)
        try:
            return self._get_items(utcnow)
        except InterfaceError:
            db.connection.close()
            return self._get_items(utcnow)

    def _get_items(self, utcnow):
        errors = PillowError.get_errors_to_process(utcnow=utcnow, limit=BATCH_SIZE)
        return list(errors)


class Command(PillowRetryEnqueuingOperation):
    pass

