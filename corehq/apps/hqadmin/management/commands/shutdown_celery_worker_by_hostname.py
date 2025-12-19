from celery import Celery
from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.hqadmin.utils import parse_celery_pings


class Command(BaseCommand):
    help = "Gracefully shuts down a celery worker"

    def add_arguments(self, parser):
        parser.add_argument('hostname')

    def handle(self, hostname, **options):
        self.celery = Celery()
        self.celery.config_from_object(settings)
        self.celery.control.broadcast('shutdown', destination=[hostname])
        if self._ping_worker(hostname):
            print('Did not shutdown worker')
            exit(1)
        print('Successfully initiated warm shutdown')

    def _ping_worker(self, hostname):
        worker_responses = self.celery.control.ping(
            timeout=10, destination=[hostname]
        )
        pings = parse_celery_pings(worker_responses)
        return hostname in pings
