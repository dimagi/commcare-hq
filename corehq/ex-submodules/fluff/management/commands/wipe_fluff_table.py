from optparse import make_option

import sqlalchemy
from django.core.management.base import BaseCommand
from dimagi.utils.modules import to_function
from django.conf import settings


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (make_option('--noinput',
                                                         action='store_true',
                                                         dest='noinput',
                                                         default=False,
                                                         help='Skip important confirmation warnings.'),)

    def handle(self, *args, **options):
        pillow_class = to_function(args[0])
        if not options['noinput']:
            confirm = raw_input("""
                You have requested to wipe %s table

                Type 'yes' to continue, or 'no' to cancel: """ % pillow_class.__name__
            )

            if confirm != 'yes':
                print "\tReset cancelled."
                return
        engine = sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)
        table_name = 'fluff_{0}'.format(pillow_class.indicator_class.__name__)
        table = sqlalchemy.Table(table_name, sqlalchemy.MetaData())
        engine.execute(table.delete())
