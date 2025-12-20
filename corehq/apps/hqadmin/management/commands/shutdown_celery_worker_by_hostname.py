from celery import Celery
from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.hqadmin.utils import parse_celery_pings


class Command(BaseCommand):
    """
    This is designed to be run from a celery machine.
    It will work from another machine as long as a broker migration
    is not in progress (i.e., some celery workers read/write to a
    different broker than the host machine this command is run on)
    """
    help = "Gracefully shuts down a celery worker"

    def add_arguments(self, parser):
        parser.add_argument('hostname')

    def handle(self, hostname, **options):
        celery = Celery()
        celery.config_from_object(settings)
        succeeded = self._shutdown(celery, hostname)
        if succeeded:
            print(f'Successfully initiated warm shutdown of {hostname}')
            return

        print(f'Did not shutdown worker {hostname}')
        exit(1)

    def _shutdown(self, celery_app, hostname):
        if not self._is_worker_up(celery_app, hostname):
            # worker not found with this celery config
            return False

        celery_app.control.broadcast('shutdown', destiation=[hostname])
        if self._is_worker_up(celery_app, hostname):
            # if worker is still up, the shutdown likely did not succeed
            # or it is just a slow shutdown
            return False

        return True

    def _is_worker_up(self, celery_app, hostname):
        worker_responses = celery_app.control.ping(
            timeout=10, destination=[hostname]
        )
        pings = parse_celery_pings(worker_responses)
        return hostname in pings
