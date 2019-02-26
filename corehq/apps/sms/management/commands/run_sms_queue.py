from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.apps.sms.models import QueuedSMS
from corehq.apps.sms.tasks import send_to_sms_queue
from corehq.sql_db.util import handle_connection_failure
from dimagi.utils.couch import get_redis_lock
from dimagi.utils.logging import notify_exception
from django.core.management.base import BaseCommand
from time import sleep


def skip_domain(domain):
    return any_migrations_in_progress(domain)


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

            self.enqueue(queued_sms)

    def enqueue(self, queued_sms):
        enqueue_lock = self.get_enqueue_lock(queued_sms)
        if enqueue_lock.acquire(blocking=False):
            send_to_sms_queue(queued_sms)

    def handle(self, **options):
        while True:
            try:
                self.create_tasks()
            except:
                notify_exception(None, message="Could not fetch due survey actions")
            sleep(10)


class Command(SMSEnqueuingOperation):
    pass
