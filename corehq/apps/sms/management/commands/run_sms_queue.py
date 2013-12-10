from datetime import datetime
from time import sleep
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from dimagi.utils.parsing import string_to_datetime, json_format_datetime
from corehq.apps.sms.models import SMSLog
from corehq.apps.sms.tasks import process_sms

class Command(BaseCommand):
    args = ""
    help = ""

    _last_datetime = datetime(1970, 1, 1)

    def populate_queue(self):
        utcnow = datetime.utcnow()
        entries = SMSLog.view(
            "sms/queued_sms",
            startkey=json_format_datetime(self._last_datetime),
            endkey=json_format_datetime(utcnow),
            limit=100,
            include_docs=False
        ).all()
        last_datetime = None
        for entry in entries:
            process_sms.delay(entry["id"])
            last_datetime = entry["key"]
        # Set self._last_datetime to the last one we got. This means
        # we'll get it again when we query next time if it's still
        # in the couch view, but that's ok because the task can handle
        # that. More importantly, we need to make sure we don't miss
        # out on any sms due to the limit parameter in the query.
        if last_datetime:
            self._last_datetime = string_to_datetime(last_datetime)

    def handle(self, *args, **options):
        if settings.SMS_QUEUE_ENABLED:
            self.validate_args(**options)
            self.keep_fetching_items()

    def validate_args(self, **options):
        pass

    def keep_fetching_items(self):
        while True:
            self.populate_queue()
            sleep(60)

