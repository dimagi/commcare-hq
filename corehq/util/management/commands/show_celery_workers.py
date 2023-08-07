from django.core.management.base import BaseCommand
from corehq.util.celery_utils import get_running_workers


class Command(BaseCommand):
    """
    Prints the names of all running celery workers. The timeout is the time in
    seconds to wait for the worker to respond to the ping command. If no timeout
    is given, a default of 10 seconds is used.

    Example usages:
    python manage.py show_celery_workers
    python manage.py show_celery_workers <timeout>
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'timeout',
            nargs='?',
            type=int,
        )

    def handle(self, timeout, **options):
        if timeout is None:
            result = get_running_workers()
        else:
            result = get_running_workers(timeout=timeout)

        if not result:
            print('(none)')
        else:
            for name in result:
                print(name)
