from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings

from corehq.toggles import DATA_MIGRATION
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.reminders.models import CaseReminder
from corehq.apps.reminders.tasks import fire_reminder
from corehq.apps.reminders.util import get_reminder_domain
from hqscripts.generic_queue import GenericEnqueuingOperation, QueueItem


class ReminderEnqueuingOperation(GenericEnqueuingOperation):
    """
    Based on our commcare-cloud code, there will be one instance of this
    command running on every machine that has a celery worker which
    consumes from the reminder_queue. This is ok because this process uses
    locks to ensure items are only enqueued once, and it's what is desired
    in order to more efficiently spawn the needed celery tasks.
    """
    help = "Runs the Reminders Queue"

    def get_fetching_interval(self):
        return 60

    def get_queue_name(self):
        return "reminders-queue"

    def get_enqueuing_timeout(self):
        return settings.REMINDERS_QUEUE_ENQUEUING_TIMEOUT

    def get_items_to_be_processed(self, utcnow):
        utcnow_json = json_format_datetime(utcnow)
        result = CaseReminder.view('reminders/by_next_fire',
            startkey=[None],
            endkey=[None, utcnow_json],
            include_docs=False,
        ).all()
        return [QueueItem(e['id'], e['key'], e) for e in result]

    def use_queue(self):
        return settings.REMINDERS_QUEUE_ENABLED

    def enqueue_item(self, item):
        domain = get_reminder_domain(item.id)
        if DATA_MIGRATION.enabled(domain):
            return
        fire_reminder.delay(item.id, domain)

    def enqueue_directly(self, reminder):
        """
        This method is used to try to send a reminder directly to the
        celery queue, without waiting for it to be enqueued by the handle()
        thread.
        """
        try:
            item = QueueItem(
                reminder._id, json_format_datetime(reminder.next_fire), reminder
            )
            self.enqueue(item)
        except:
            # If anything goes wrong here, no problem, the handle() thread will
            # pick it up later and enqueue.
            pass


class Command(ReminderEnqueuingOperation):
    pass

