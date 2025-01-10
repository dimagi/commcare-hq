from django.core.management.base import BaseCommand

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.motech.repeaters.const import PROCESS_REPEATERS_KEY


class Command(BaseCommand):
    help = """
    If the `process_repeaters()` task was killed and the lock was not
    released, this command expires the lock and allows the task to start.
    """

    def handle(self, domain, repeater_id, *args, **options):
        client = get_redis_client()
        client.expire(PROCESS_REPEATERS_KEY, timeout=0)
