from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime
import argparse

from django.core.management.base import BaseCommand

from custom.icds_reports.reports.disha import build_dumps_for_month


class Command(BaseCommand):
    help = "Build DISHA data dumps for given month"

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
            '--force-rebuild',
            action='store_true',
            default=False,
            dest='rebuild',
            help='If True, dump is built for all states, otherwise only for missing states',
        )

    def handle(self, month, rebuild, *args, **kwargs):
        build_dumps_for_month(month, rebuild)
