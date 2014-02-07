from optparse import make_option
from django.core.management.base import CommandError
from django.conf import settings
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.sms.models import SMSLog
from corehq.apps.sms.tasks import process_sms
from hqscripts.generic_queue import GenericEnqueuingOperation

class SMSEnqueuingOperation(GenericEnqueuingOperation):
    args = ""
    help = "Runs the SMS Queue"

    def get_queue_name(self):
        return "sms-queue"

    def get_enqueuing_timeout(self):
        return settings.SMS_QUEUE_ENQUEUING_TIMEOUT

    def get_items_to_be_processed(self, utcnow):
        # We're just querying for ids here, so no need to limit
        entries = SMSLog.view(
            "sms/queued_sms",
            startkey="1970-01-01T00:00:00Z",
            endkey=json_format_datetime(utcnow),
            include_docs=False
        ).all()
        return entries

    def use_queue(self):
        return settings.SMS_QUEUE_ENABLED

    def enqueue_item(self, _id):
        process_sms.delay(_id)

    def enqueue_directly(self, msg):
        """
        This method is used to try to send an SMSLog entry directly to the
        celery queue, without waiting for it to be enqueued by the handle()
        thread.
        """
        try:
            self.enqueue(msg._id, json_format_datetime(msg.datetime_to_process))
        except:
            # If anything goes wrong here, no problem, the handle() thread will
            # pick it up later and enqueue.
            pass

class Command(SMSEnqueuingOperation):
    pass

