from django.core.management.base import BaseCommand

from corehq.apps.data_analytics.malt_generator import MALTTableGenerator
from dimagi.utils.dates import DateSpan, safe_strftime

import dateutil


class Command(BaseCommand):
    """
        Note: Expectes to be called, once, after the month ends,...
        to avoid duplicates. If not, this will raise IntegrityError
    """
    help = 'Rebuilds MALT table for given month'
    args = '<month_year>'

    def handle(self, *args, **options):
        month_year = dateutil.parser.parse(args[0])
        datespan = DateSpan.from_month(month_year.month, month_year.year)
        generator = MALTTableGenerator(datespan)
        print "Building Malt table for {}...".format(safe_strftime(month_year, '%b-%Y'))
        generator.build_table()
        print "Finished!"
