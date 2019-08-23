from django.core.management.base import BaseCommand
from django.conf import settings
from celery import Celery

from corehq.apps.hqadmin.utils import parse_celery_pings


class Command(BaseCommand):
    help = "Gracefully shutsdown a celery worker"

    def add_arguments(self, parser):
        parser.add_argument('hostname')

    def handle(self, hostname, **options):
        celery = Celery()
        celery.config_from_object(settings)
        celery.control.broadcast('shutdown', destination=[hostname])
        worker_responses = celery.control.ping(timeout=10, destination=[hostname])
        pings = parse_celery_pings(worker_responses)
        if hostname in pings:
            print('Did not shutdown worker')
            exit(1)
        print('Successfully initiated warm shutdown')
