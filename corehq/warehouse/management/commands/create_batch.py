from __future__ import absolute_import, print_function

from datetime import datetime

from django.core.management import BaseCommand, CommandError

from corehq.util.argparse_types import utc_timestamp
from corehq.warehouse.models import Batch
from dimagi.utils.parsing import string_to_utc_datetime


USAGE = """Usage: ./manage.py create_batch <dag_slug> <end_date>
"""


class Command(BaseCommand):
    """
    Example: ./manage.py create_batch app_status
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('dag_slug')
        parser.add_argument('end_date', type=utc_timestamp)

    def handle(self, dag_slug, end_date,  **options):
        last_batch = Batch.objects.filter(dag_slug=dag_slug, completed_on__isnull=False).order_by('-end_datetime').first()
        start = last_batch.end_datetime if last_batch else '2000-01-01'

        new_batch = Batch.objects.create(
            start_datetime=start,
            end_datetime=end_date,
            dag_slug=dag_slug
        )
        print(new_batch.id)
