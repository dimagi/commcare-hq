from __future__ import absolute_import
from datetime import date
from django.core.management import BaseCommand
from corehq.warehouse.models import Batch


USAGE = """Usage: ./manage.py create_batch
"""


class Command(BaseCommand):
    """
    Example: ./manage.py create_batch
    """
    help = USAGE

    def handle(self, **options):
        last_batch = Batch.objects.filter(completed_on__isnull=False).order_by('-end_datetime').first()
        start = last_batch.end_datetime
        end = date.today()

        new_batch = Batch.objects.create(
            start_datetime=start,
            end_datetime=end,
        )
        print(new_batch.id)
