from __future__ import absolute_import
from datetime import datetime
from django.core.management import BaseCommand
from corehq.warehouse.models import Batch


USAGE = """Usage: ./manage.py create_batch <dag_slug>
"""


class Command(BaseCommand):
    """
    Example: ./manage.py create_batch app_status
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('dag_slug')

    def handle(self, dag_slug, **options):
        last_batch = Batch.objects.filter(dag_slug=dag_slug, completed_on__isnull=False).order_by('-end_datetime').first()
        start = last_batch.end_datetime if last_batch else '2000-01-01'
        end = datetime.utcnow()

        new_batch = Batch.objects.create(
            start_datetime=start,
            end_datetime=end,
            dag_slug=dag_slug
        )
        print(new_batch.id)


