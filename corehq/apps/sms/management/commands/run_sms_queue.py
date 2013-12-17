from optparse import make_option
from django.core.management.base import CommandError
from django.conf import settings
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.sms.models import SMSLog
from corehq.apps.sms.tasks import process_sms
from hqscripts.generic_queue import GenericEnqueuingOperation

class Command(GenericEnqueuingOperation):
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

    def enqueue(self, _id):
        process_sms.delay(_id)

