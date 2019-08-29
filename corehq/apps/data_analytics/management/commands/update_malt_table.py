from django.core.management.base import BaseCommand

import dateutil

from dimagi.utils.dates import DateSpan

from corehq.apps.data_analytics.malt_generator import MALTTableGenerator


class Command(BaseCommand):
    """
        Generates malt table for given list of months (at least one month required)
        e.g. ./manage.py update_malt_table June-2015 May-2015
    """
    help = 'Rebuilds MALT table for given months'

    def add_arguments(self, parser):
        parser.add_argument(
            'month_years',
            metavar='month_year',
            nargs='+',
        )

    def handle(self, month_years, **options):
        datespan_list = []
        for arg in month_years:
            month_year = dateutil.parser.parse(arg)
            datespan_list.append(DateSpan.from_month(month_year.month, month_year.year))
        generator = MALTTableGenerator(datespan_list)
        print("Building Malt table... for time range {}".format(datespan_list))
        generator.build_table()
        print("Finished!")
