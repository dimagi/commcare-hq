from django.core.management.base import BaseCommand

from corehq.apps.data_analytics.gir_generator import GIRTableGenerator
from dimagi.utils.dates import DateSpan

import dateutil


class Command(BaseCommand):
    """
        Generates GIR table for given list of months (at least one month required)
        e.g. ./manage.py update_gir_table June-2015 May-2015
    """
    help = 'Rebuilds GIR table for given months'
    args = '<month_year> <month_year> <month_year> ...'

    def handle(self, *args, **options):
        datespan_list = []
        for arg in args:
            month_year = dateutil.parser.parse(arg)
            datespan_list.append(DateSpan.from_month(month_year.month, month_year.year))
        generator = GIRTableGenerator(datespan_list)
        print "Building GIR table... for time range {}".format(datespan_list)
        generator.build_table()
        print "Finished!"
