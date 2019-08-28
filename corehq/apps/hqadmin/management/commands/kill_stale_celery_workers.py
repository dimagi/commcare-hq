
from django.conf import settings
from django.core.management.base import BaseCommand

import requests
from celery import Celery

from corehq.apps.hqadmin.utils import parse_celery_pings, parse_celery_workers


class Command(BaseCommand):
    help = "Kills stale celery workers"

    def handle(self, **options):
        _kill_stale_workers()


def _kill_stale_workers():
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    if celery_monitoring:
        all_workers = requests.get(
            celery_monitoring + '/api/workers',
            params={'status': True},
            timeout=3,
        ).json()
        expected_running, expected_stopped = parse_celery_workers(all_workers)

        celery = Celery()
        celery.config_from_object(settings)
        worker_responses = celery.control.ping(timeout=10)
        pings = parse_celery_pings(worker_responses)

        hosts_to_stop = [hostname for hostname in expected_stopped if hostname in pings]
        if hosts_to_stop:
            celery.control.broadcast('shutdown', destination=hosts_to_stop)
