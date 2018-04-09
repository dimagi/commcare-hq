from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand, CommandError
from dimagi.utils.parsing import string_to_utc_datetime
from corehq.warehouse.models import Batch


USAGE = """Usage: ./manage.py create_batch <batch_id> -s <start_datetime> -e <end_datetime>
"""


class Command(BaseCommand):
    """
    Example: ./manage.py create_batch 222617b9-8cf0-40a2-8462-7f872e1f1344 -s 2017-05-01 -e 2017-06-01
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('batch_id')

        parser.add_argument(
            '-s',
            '--start_datetime',
            dest='start',
            required=True,
            help='Specifies the last modified datetime at which records should start being included',
            type=_valid_date
        )
        parser.add_argument(
            '-e',
            '--end_datetime',
            dest='end',
            required=True,
            help='Specifies the last modified datetime at which records should stop being included',
            type=_valid_date
        )

    def handle(self, batch_id, **options):
        start = options.get('start')
        end = options.get('end')

        Batch.objects.create(
            batch_id=batch_id,
            start_datetime=start,
            end_datetime=end,
        )


def _valid_date(date_str):
    try:
        return string_to_utc_datetime(date_str)
    except ValueError:
        raise CommandError('Not a valid date string: {}'.format(date_str))
