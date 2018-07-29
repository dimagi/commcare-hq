from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from fluff.pillow import FluffPillowProcessor
from pillowtop.utils import get_pillow_by_name
from six.moves import input


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'pillow_name',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.',
        )

    def handle(self, pillow_name, **options):
        pillow = get_pillow_by_name(pillow_name)
        if not options['noinput']:
            confirm = input(
                """
                You have requested to wipe %s table

                Type 'yes' to continue, or 'no' to cancel:
                """ % pillow.pillow_id
            )

            if confirm != 'yes':
                print("\tWipe cancelled.")
                return

        for processor in pillow.processors:
            engine = processor.get_sql_engine()
            table = processor.indicator_class().table
            engine.execute(table.delete())
