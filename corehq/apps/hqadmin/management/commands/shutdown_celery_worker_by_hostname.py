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

        current_broker_url = getattr(settings, 'CELERY_BROKER_URL', None)
        assert current_broker_url is not None, "CELERY_BROKER_URL is not set"

        # as long as OLD_BROKER_URL is set, we are going to send shutdown
        # broadcasts to both the old and new broker urls
        old_broker_url = getattr(settings, 'OLD_BROKER_URL', None)
        migration_in_progress = old_broker_url is not None

        if not migration_in_progress:
            succeeded = self._shutdown(hostname)
            if succeeded:
                print(f'Successfully initiated warm shutdown of {hostname}')
                return
            exit(1)

        for broker_url in [current_broker_url, old_broker_url]:
            broker_conn = Connection(broker_url)
            succeeded = self._shutdown(hostname, broker_conn)
            broker_conn.release()
            if succeeded:
                print(
                    '[Broker Migration In Progress] Initiated warm shutdown '
                    f'of {hostname}'
                )

    def _shutdown(self, hostname, broker_conn=None):
        # if using a custom broker connection, it is unlikely a ping will
        # work properly since the worker might be writing to a different
        # broker than the one it is reading from
        check_worker_up = broker_conn is None

        if check_worker_up and not self._is_worker_up(hostname):
            print(f'{hostname} did not respond to ping. Aborted shutdown.')
            return False

        kwargs = {'destination': [hostname]}
        if broker_conn is not None:
            # use a custom broker connection
            kwargs['connection'] = broker_conn
        self.celery.control.broadcast('shutdown', **kwargs)

        if check_worker_up and self._is_worker_up(hostname):
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
