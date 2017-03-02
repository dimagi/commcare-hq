from __future__ import print_function
from optparse import make_option

from django.core.management.base import BaseCommand

from fluff.pillow import FluffPillowProcessor
from pillowtop.utils import get_pillow_by_name


class Command(BaseCommand):

    option_list = (
        make_option('--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.'),
    )

    def handle(self, *args, **options):
        pillow = get_pillow_by_name(args[0])
        if not options['noinput']:
            confirm = raw_input(
                """
                You have requested to wipe %s table

                Type 'yes' to continue, or 'no' to cancel:
                """ % pillow.pillow_id
            )

            if confirm != 'yes':
                print("\tWipe cancelled.")
                return

        processor = FluffPillowProcessor(pillow.indicator_class)
        engine = processor.get_sql_engine()
        table = pillow.indicator_class().table
        engine.execute(table.delete())
