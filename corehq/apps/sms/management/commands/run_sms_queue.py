from __future__ import absolute_import
from django.conf import settings

from corehq.toggles import DATA_MIGRATION
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.sms.models import QueuedSMS
from corehq.apps.sms.tasks import process_sms
from hqscripts.generic_queue import GenericEnqueuingOperation


class SMSEnqueuingOperation(GenericEnqueuingOperation):
    help = "Runs the SMS Queue"

    def get_queue_name(self):
        return "sms-queue"

    def get_enqueuing_timeout(self):
        return settings.SMS_QUEUE_ENQUEUING_TIMEOUT

    def get_items_to_be_processed(self, utcnow):
        for sms in QueuedSMS.get_queued_sms():
            if DATA_MIGRATION.enabled(sms.domain):
                continue
            yield {
                'id': sms.pk,
                'key': json_format_datetime(sms.datetime_to_process),
            }

    def use_queue(self):
        return settings.SMS_QUEUE_ENABLED

    def enqueue_item(self, pk):
        process_sms.delay(pk)

    def enqueue_directly(self, sms):
        """
        This method is used to try to send a QueuedSMS entry directly to the
        celery queue, without waiting for it to be enqueued by the handle()
        thread.
        """
        try:
            self.enqueue(sms.pk, json_format_datetime(sms.datetime_to_process))
        except:
            # If anything goes wrong here, no problem, the handle() thread will
            # pick it up later and enqueue.
            pass


class Command(SMSEnqueuingOperation):
    pass
