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
            print(f'Successfully initiated warm shutdown of {hostname}')
            return

        exit(1)

    def _shutdown(self, hostname, broker_conn=None):
        # a worker configured to read from the old broker and write to the new
        # broker will be unable to respond to a ping on the custom broker_conn
        # so just skip it if using a custom broker_conn
        check_worker_up = broker_conn is None
        if check_worker_up and not self._is_worker_up(hostname, broker_conn):
            print(f'{hostname} did not respond to ping. Aborted shutdown.')
            return False

        kwargs = {'destination': [hostname]}
        if broker_conn is not None:
            # use a custom broker connection
            kwargs['connection'] = broker_conn
        self.celery.control.broadcast('shutdown', **kwargs)

        if check_worker_up and self._is_worker_up(hostname, broker_conn):
            # if worker is still up, the shutdown likely did not succeed
            # or it is just a slow shutdown
            print(f'{hostname} responded to ping after initiating shutdown.')
            return False

        return True

    def _is_worker_up(self, hostname):
        worker_responses = self.celery.control.ping(
            timeout=10, destination=[hostname]
        )
        pings = parse_celery_pings(worker_responses)
        return hostname in pings
