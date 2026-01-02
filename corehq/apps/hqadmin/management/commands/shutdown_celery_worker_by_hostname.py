from contextlib import contextmanager

from celery import Celery
from django.conf import settings
from django.core.management.base import BaseCommand
from kombu import Connection

from corehq.apps.hqadmin.utils import parse_celery_pings


class Command(BaseCommand):
    """
    The complexity here is to accommodate migrating celery brokers
    If in the future it becomes a challenge to support custom connections,
    removing that logic here should be fine. The downside is that when
    switching brokers, celery workers configured to read/write to the old
    broker will not shutdown properly.
    """
    help = "Gracefully shuts down a celery worker"

    def add_arguments(self, parser):
        parser.add_argument('hostname')

    def handle(self, hostname, **options):
        self.celery = Celery()
        self.celery.config_from_object(settings)

        current_broker_url = getattr(settings, 'CELERY_BROKER_URL', None)
        assert current_broker_url is not None, "CELERY_BROKER_URL is not set"
        broker_urls = [current_broker_url]
        if old_broker_url := getattr(settings, 'OLD_BROKER_URL', None):
            broker_urls.append(old_broker_url)

        success = False
        for broker_url in broker_urls:
            with self._connection(broker_url) as conn:
                success = self._shutdown_worker(hostname, conn)
            if success:
                break

        if not success:
            print(f'Failed to shutdown {hostname}.')
            exit(1)

    def _shutdown_worker(self, hostname, conn):
        if not self._ping_worker(hostname, conn):
            print(f'Failed to ping {hostname} via broker at {conn.hostname}')
            return False

        self.celery.control.broadcast('shutdown', destination=[hostname])

        if self._ping_worker(hostname, conn):
            print(
                f'Sent shutdown to {hostname} but worker is still '
                'responding to ping'
            )
        print(f'Successfully shutdown {hostname}')
        return True

    def _ping_worker(self, hostname, conn):
        worker_responses = self.celery.control.ping(
            timeout=10, destination=[hostname], connection=conn
        )
        pings = parse_celery_pings(worker_responses)
        return hostname in pings

    @contextmanager
    def _connection(self, url):
        conn = Connection(url)
        try:
            yield conn
        finally:
            conn.release()
