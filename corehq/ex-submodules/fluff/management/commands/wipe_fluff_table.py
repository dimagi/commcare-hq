from optparse import make_option

from django.core.management.base import BaseCommand
from pillowtop.utils import get_pillow_by_name


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (make_option('--noinput',
                                                         action='store_true',
                                                         dest='noinput',
                                                         default=False,
                                                         help='Skip important confirmation warnings.'),)

    def handle(self, *args, **options):
        pillow_class = get_pillow_by_name(args[0], instantiate=False)
        if not options['noinput']:
            confirm = raw_input(
                """
                You have requested to wipe %s table

                Type 'yes' to continue, or 'no' to cancel:
                """ % pillow_class.__name__
            )

            if confirm != 'yes':
                print "\tWipe cancelled."
                return
        engine = pillow_class.get_sql_engine()
        table = pillow_class.indicator_class().table
        engine.execute(table.delete())
