from django.core.management.base import BaseCommand

import dateutil

from dimagi.utils.dates import DateSpan

from corehq.apps.data_analytics.malt_generator import generate_malt
from corehq.apps.domain.models import Domain


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
        parser.add_argument('--start-domain', dest='start_domain')

    def handle(self, month_years, **options):
        datespan_list = []
        for arg in month_years:
            month_year = dateutil.parser.parse(arg)
            datespan_list.append(DateSpan.from_month(month_year.month, month_year.year))
        print("Building Malt table... for time range {}".format(datespan_list))
        if options['start_domain']:
            domains = Domain.get_all_names()
            start_index = domains.index(options['start_domain'])
            generate_malt(datespan_list, domains=domains[start_index:])
        else:
            generate_malt(datespan_list)
        print("Finished!")
