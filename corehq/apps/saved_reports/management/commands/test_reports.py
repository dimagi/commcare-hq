from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.saved_reports.tasks import queue_scheduled_reports


class Command(BaseCommand):
    help = "Tests sending reports. Equivalent to firing the celery tasks right NOW."

    def handle(self, **options):
        queue_scheduled_reports()
