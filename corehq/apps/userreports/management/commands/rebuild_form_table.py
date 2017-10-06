from __future__ import print_function
from datetime import datetime, timedelta
import argparse

from django.core.management.base import BaseCommand

from corehq.apps.userreports.tasks import rebuild_form_table


class Command(BaseCommand):
    help = "Rebuild a table in place for forms in a specific time period"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('indicator_config_id')
        parser.add_argument('start_date', help="YYYY-MM-DD")
        parser.add_argument('end_date', help="YYYY-MM-DD")
        parser.add_argument('xmlns_list', nargs=argparse.REMAINDER)

    def handle(self, domain, indicator_config_id, start_date, end_date, xmlns_list, **options):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        rebuild_form_table.delay(domain, indicator_config_id, start_date, end_date, xmlns_list)
