from celery import Celery
from django.conf import settings
from django.core.management.base import BaseCommand
from kombu import Connection

from corehq.apps.hqadmin.utils import parse_celery_pings


class Command(BaseCommand):
    help = "Gracefully shuts down a celery worker"

    def add_arguments(self, parser):
        parser.add_argument('hostname')

    def handle(self, hostname, **options):
        self.celery = Celery()
        self.celery.config_from_object(settings)

        broker_conn = None
        # explicit read and write urls are only set when a broker
        # migration is in progress
        if old_broker_url := getattr(settings, 'CELERY_BROKER_READ_URL', None):
            broker_conn = Connection(old_broker_url)

        succeeded = self._shutdown(hostname, broker_conn)
        if succeeded:
            print('Successfully initiated warm shutdown')
            return

        print(f'Did not shutdown worker {hostname}')
        exit(1)

    def _shutdown(self, hostname, broker_conn=None):
        kwargs = {'destination': [hostname]}
        if broker_conn is not None:
            # use a custom broker connection
            kwargs['broker'] = broker_conn
        self.celery.control.broadcast('shutdown', **kwargs)

        if broker_conn is None:
            worker_responses = self.celery.control.ping(
                timeout=10, destination=[hostname]
            )
            pings = parse_celery_pings(worker_responses)
            if hostname in pings:
                return False
            return True
        return True
