from django.conf import settings
from corehq.apps.pillow_retry.tasks import process_pillow_retry
from hqscripts.generic_queue import GenericEnqueuingOperation
from pillow_retry.models import PillowError


class PillowRetryEnqueuingOperation(GenericEnqueuingOperation):
    args = ""
    help = "Runs the Pillow Retry Queue"

    def get_queue_name(self):
        return "pillow-queue"

    def get_enqueuing_timeout(self):
        return settings.PILLOW_RETRY_QUEUE_ENQUEUING_TIMEOUT

    def get_items_to_be_processed(self, utcnow):
        # We're just querying for ids here, so no need to limit
        errors = PillowError.get_errors_to_process(
            utcnow=utcnow,
        )
        return errors

    def use_queue(self):
        return settings.PILLOW_RETRY_QUEUE_ENABLED

    def enqueue_item(self, item_id):
        process_pillow_retry.delay(item_id)


class Command(PillowRetryEnqueuingOperation):
    pass

