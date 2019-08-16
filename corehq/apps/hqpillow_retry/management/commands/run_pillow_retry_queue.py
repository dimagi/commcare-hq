from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from psycopg2._psycopg import InterfaceError
import pytz
from hqscripts.generic_queue import GenericEnqueuingOperation, QueueItem
from pillow_retry.const import PILLOW_RETRY_QUEUE_ENQUEUING_TIMEOUT
from pillow_retry.models import PillowError
from pillow_retry.api import process_pillow_retry
from django import db


class PillowRetryEnqueuingOperation(GenericEnqueuingOperation):
    help = "Runs the Pillow Retry Queue"
    _errors_in_queue = False

    def get_fetching_interval(self):
        return 0 if self._errors_in_queue else 10

    def get_queue_name(self):
        return "pillow-queue"

    def get_enqueuing_timeout(self):
        return PILLOW_RETRY_QUEUE_ENQUEUING_TIMEOUT

    def _get_items(self, utcnow):
        errors = PillowError.get_errors_to_process(utcnow=utcnow, limit=10000)
        items = [QueueItem(id=e.id, key=e.date_next_attempt, object=e) for e in errors]
        self._errors_in_queue = bool(items)
        return items

    def get_items_to_be_processed(self, utcnow):
        # We're just querying for ids here, so no need to limit
        utcnow = utcnow.replace(tzinfo=pytz.UTC)
        try:
            return self._get_items(utcnow)
        except InterfaceError:
            db.connection.close()
            return self._get_items(utcnow)

    def use_queue(self):
        return settings.PILLOW_RETRY_QUEUE_ENABLED

    def enqueue_item(self, item):
        process_pillow_retry(item.object)


class Command(PillowRetryEnqueuingOperation):
    pass

