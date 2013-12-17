from datetime import datetime
from time import sleep
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from dimagi.utils.parsing import string_to_datetime, json_format_datetime
from corehq.apps.sms.models import SMSLog
from corehq.apps.sms.tasks import process_sms
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.logging import notify_exception

class RedisClientError(Exception):
    pass

class Command(BaseCommand):
    args = ""
    help = "Runs the SMS Queue"

    def populate_queue(self):
        client = self.get_redis_client()
        utcnow = datetime.utcnow()
        entries = self.get_items_to_be_processed(utcnow)
        for entry in entries:
            queue_name = self.get_queue_name()
            entry_id = entry["id"]
            process_datetime = entry["key"]
            enqueuing_lock = self.get_enqueuing_lock(client,
                "%s-enqueuing-%s-%s" % (queue_name, entry_id, process_datetime))
            if enqueuing_lock.acquire(blocking=False):
                try:
                    self.enqueue(entry_id)
                except:
                    # We couldn't enqueue, so release the lock
                    enqueuing_lock.release()

    def get_redis_client(self):
        rcache = cache_core.get_redis_default_cache()
        if not isinstance(rcache, RedisCache):
            raise RedisClientError("Could not get redis connection.")
        try:
            client = rcache.raw_client
        except:
            raise RedisClientError("Could not get redis connection.")
        return client

    def get_enqueuing_lock(client, key):
        lock_timeout = self.get_enqueuing_timeout()
        return client.lock(key, timeout=lock_timeout)

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

    def handle(self, *args, **options):
        if self.use_queue():
            self.validate_args(**options)
            self.keep_fetching_items()

    def validate_args(self, **options):
        pass

    def keep_fetching_items(self):
        while True:
            try:
                self.populate_queue()
            except RedisClientError:
                notify_exception(None,
                    message="Could not get redis connection. Is redis up?")
            except:
                notify_exception(None,
                    message="Could not populate %s." % self.get_queue_name())
            sleep(15)

