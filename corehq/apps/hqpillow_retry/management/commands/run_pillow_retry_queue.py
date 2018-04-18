from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from psycopg2._psycopg import InterfaceError
import pytz
from hqscripts.generic_queue import GenericEnqueuingOperation
from pillow_retry.models import PillowError
from pillow_retry.tasks import process_pillow_retry
from django import db


class PillowRetryEnqueuingOperation(GenericEnqueuingOperation):
    help = "Runs the Pillow Retry Queue"

    def get_queue_name(self):
        return "pillow-queue"

    def get_enqueuing_timeout(self):
        return settings.PILLOW_RETRY_QUEUE_ENQUEUING_TIMEOUT

    @staticmethod
    def _get_items(utcnow):
        errors = PillowError.get_errors_to_process(utcnow=utcnow, limit=1000)
        return [dict(id=e['id'], key=e['date_next_attempt']) for e in errors]

    @classmethod
    def get_items_to_be_processed(cls, utcnow):
        # We're just querying for ids here, so no need to limit
        utcnow = utcnow.replace(tzinfo=pytz.UTC)
        try:
            return cls._get_items(utcnow)
        except InterfaceError:
            db.connection.close()
            return cls._get_items(utcnow)

    def use_queue(self):
        return settings.PILLOW_RETRY_QUEUE_ENABLED

    def enqueue_item(self, item_id):
        process_pillow_retry.delay(item_id)


class Command(PillowRetryEnqueuingOperation):
    pass

