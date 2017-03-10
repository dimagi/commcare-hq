from django.core.management.base import BaseCommand, CommandError
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
    args = '<timeout>'
    help = ''

    def handle(self, *args, **options):
        if len(args) == 0:
            result = get_running_workers()
        else:
            timeout = args[0]
            try:
                timeout = int(timeout)
            except (ValueError, TypeError):
                raise CommandError("Error: Timeout seconds must be an integer")

            result = get_running_workers(timeout=timeout)

        if not result:
            print '(none)'
        else:
            for name in result:
                print name
