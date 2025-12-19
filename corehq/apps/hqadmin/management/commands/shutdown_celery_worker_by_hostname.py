from celery import Celery
from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.hqadmin.utils import parse_celery_pings


class Command(BaseCommand):
    help = "Gracefully shuts down a celery worker"

    def add_arguments(self, parser):
        parser.add_argument('hostname')

    def handle(self, hostname, **options):
        celery = Celery()
        celery.config_from_object(settings)
        succeeded = self._shutdown(celery, hostname)
        if succeeded:
            print('Successfully initiated warm shutdown')
            return

        # try old broker if it is set
        if settings.OLD_BROKER_URL:
            old_celery_app = Celery()
            old_celery_app.config_from_object(settings)
            old_celery_app.conf.broker_url = settings.OLD_BROKER_URL
            succeeded = self._shutdown(old_celery_app, hostname)
            if succeeded:
                print('Successfully initiated warm shutdown via old broker')
                return

        print(f'Did not shutdown worker {hostname}')
        exit(1)

    def _shutdown(self, celery_app, hostname):
        celery_app.control.broadcast('shutdown', destiation=[hostname])
        worker_responses = celery_app.control.ping(
            timeout=10, destination=[hostname]
        )
        pings = parse_celery_pings(worker_responses)
        if hostname in pings:
            return False
        return True
