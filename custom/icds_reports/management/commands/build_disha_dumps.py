from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime
import argparse

from django.core.management.base import BaseCommand

from custom.icds_reports.reports.disha import build_dumps_for_month
from dimagi.utils.dates import add_months_to_date


class Command(BaseCommand):
    help = "Build DISHA data dumps for given month for all states"

    def add_arguments(self, parser):
        def valid_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d").date().replace(day=1)
            except ValueError:
                msg = "Not a valid date: '{0}'.".format(s)
                raise argparse.ArgumentTypeError(msg)

        parser.add_argument(
            'month',
            type=valid_date,
            help="Month of DISHA dump - format = YYYY-MM-DD",
        )
        parser.add_argument(
            '--extra_months',
            type=int,
            action="store",
            dest="extra_months",
            default=0,
            help="Also build for next extra_months from month"
        )
        parser.add_argument(
            '--force-rebuild',
            action='store_true',
            default=False,
            dest='rebuild',
            help='Rebuilds dumps. Default is to skip if a state has a dump built',
        )

    def handle(self, month, rebuild, *args, **kwargs):
        print("Building for month {}".format(str(month)))
        build_dumps_for_month(month, rebuild)
        extra_months = kwargs.get('extra_months', 0)
        for i in range(extra_months):
            extra_month = add_months_to_date(month, i + 1)
            assert extra_month < datetime.today().date(), "Building for future months is not a valid operation"
            print("Building for extra month {}".format(str(extra_month)))
            build_dumps_for_month(extra_month, rebuild)
