from django.core.management.base import CommandError
from django.conf import settings
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.reminders.tasks import fire_reminder
from hqscripts.generic_queue import GenericEnqueuingOperation

class ReminderEnqueuingOperation(GenericEnqueuingOperation):
    args = ""
    help = "Runs the Reminders Queue"

    def get_queue_name(self):
        return "reminders-queue"

    def get_enqueuing_timeout(self):
        return settings.REMINDERS_QUEUE_ENQUEUING_TIMEOUT

    def get_items_to_be_processed(self, utcnow):
        # We're just querying for ids here, so no need to limit
        return CaseReminderHandler.get_all_reminders(due_before=utcnow,
            ids_only=True)

    def use_queue(self):
        return settings.REMINDERS_QUEUE_ENABLED

    def enqueue_item(self, _id):
        fire_reminder.delay(_id)

    def enqueue_directly(self, reminder):
        """
        This method is used to try to send a reminder directly to the
        celery queue, without waiting for it to be enqueued by the handle()
        thread.
        """
        try:
            self.enqueue(reminder._id, json_format_datetime(reminder.next_fire))
        except:
            # If anything goes wrong here, no problem, the handle() thread will
            # pick it up later and enqueue.
            pass

class Command(ReminderEnqueuingOperation):
    pass

