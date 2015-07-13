from django.core.management.base import BaseCommand

from corehq.apps.data_analytics.malt_generator import MALTTableGenerator
from dimagi.utils.dates import DateSpan

import dateutil


class Command(BaseCommand):
    """
        Generates malt table for given list of months (at least one month required)
        e.g. ./manage.py update_malt_table June-2015 May-2015
    """
    help = 'Rebuilds MALT table for given months'
    args = '<month_year> <month_year> <month_year> ...'

    def handle(self, *args, **options):
        datespan_list = []
        for arg in args:
            month_year = dateutil.parser.parse(arg)
            datespan_list.append(DateSpan.from_month(month_year.month, month_year.year))
        generator = MALTTableGenerator(datespan_list)
        print "Building Malt table..."
        generator.build_table()
        print "Finished!"
