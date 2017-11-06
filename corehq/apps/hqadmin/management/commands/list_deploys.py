from __future__ import print_function
from __future__ import absolute_import
from datetime import datetime
from dateutil import parser

from django.core.management.base import BaseCommand
from corehq.apps.hqadmin.models import HqDeploy


class Command(BaseCommand):
    help = "Print a list of code deploys between dates"

    def add_arguments(self, parser):
        parser.add_argument(
            '--start',
            action='store',
            dest='startdate',
            default='',
            help='Start date',
        )
        parser.add_argument(
            '--end',
            action='store',
            dest='enddate',
            default='',
            help='End date (defaults to now)',
        )

    def handle(self, **options):
        start = parser.parse(options['startdate'])
        enddate = options['enddate']
        end = parser.parse(enddate) if enddate else datetime.utcnow()

        ds = HqDeploy.get_list('production', start, end)
        ids = [d['id'] for d in ds]
        sha_prev = None
        print_row('Deploy Date', "Commit Date", "Diff")
        for id in ids:
            d = HqDeploy.get(id)
            s = d.code_snapshot['commits'][0]
            sha = s['sha']
            url = "https://github.com/dimagi/commcare-hq/compare/{sha_prev}...{sha}".format(
                sha=sha,
                sha_prev=sha_prev
            )
            print_row(d.date, s['date'], url)
            sha_prev = sha


def print_row(*args):
    tp = ["{{{}!s:<30}}".format(i) for i, _ in enumerate(args)]
    template = ' | '.join(tp)
    print(template.format(*args))
