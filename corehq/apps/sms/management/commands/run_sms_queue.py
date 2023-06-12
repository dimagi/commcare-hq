import pytz
import datetime
from time import sleep

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.functional import cached_property

from dimagi.utils.couch import get_redis_lock
from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.models import Domain
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.apps.sms.api import get_utcnow
from corehq.apps.sms.models import QueuedSMS
from corehq.apps.sms.tasks import send_to_sms_queue, time_within_windows
from corehq.sql_db.util import handle_connection_failure
from corehq.util.timezones.conversions import ServerTime
from custom.icds.utils.sms import can_send_sms_now

india_timezone = pytz.timezone('Asia/Kolkata')


def skip_domain(domain):
    if any_migrations_in_progress(domain):
        return True


class SMSEnqueuingOperation(BaseCommand):
    """
    Based on our commcare-cloud code, there will be one instance of this
    command running on every machine that has a celery worker which
    consumes from the sms_queue. This is ok because this process uses
    locks to ensure items are only enqueued once, and it's what is desired
    in order to more efficiently spawn the needed celery tasks.
    """
    help = "Spawns tasks to process queued SMS"

    def get_enqueue_lock(self, queued_sms):
        key = "create-task-for-sms-%s-%s" % (
            queued_sms.pk,
            queued_sms.datetime_to_process.strftime('%Y-%m-%d %H:%M:%S')
        )
        return get_redis_lock(
            key,
            timeout=3 * 60 * 60,
            name="sms_task",
            track_unreleased=False,
        )

    @handle_connection_failure()
    def create_tasks(self):
        for queued_sms in QueuedSMS.get_queued_sms():
            if queued_sms.domain and skip_domain(queued_sms.domain):
                continue

            if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS and not can_send_sms_now():
                break
            self.enqueue(queued_sms)

    def enqueue(self, queued_sms):
        enqueue_lock = self.get_enqueue_lock(queued_sms)
        if enqueue_lock.acquire(blocking=False):
            send_to_sms_queue(queued_sms)

    def handle(self, **options):
        while True:
            try:
                if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS and not can_send_sms_now():
                    sleep(self._time_till_next_window())
                else:
                    self.create_tasks()
            except:
                notify_exception(None, message="Could not fetch due survey actions")
            sleep(10)

    def _time_till_next_window(self):
        # if from time is greater than the start_time, it would give seconds till next day start
        server_now_time = self._get_server_time()
        today = datetime.date.today()
        from_datetime = datetime.datetime.combine(today, server_now_time)
        to_datetime = datetime.datetime.combine(today, datetime.time(9, 0))
        return (to_datetime - from_datetime).seconds

    def _get_server_time(self):
        utcnow = get_utcnow()
        server_now = ServerTime(utcnow).user_time(india_timezone).done()
        return server_now.time()


class Command(SMSEnqueuingOperation):
    pass
