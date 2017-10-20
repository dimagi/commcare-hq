from __future__ import print_function
from datetime import datetime, timedelta
import argparse

from django.core.management.base import BaseCommand

from corehq.apps.userreports.tasks import rebuild_indicators_in_place
from couchforms.dbaccessors import get_form_ids_by_type


class Command(BaseCommand):
    help = "Rebuild a table in place for forms in a specific time period"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('indicator_config_id')
        parser.add_argument('start_date', help="YYYY-MM-DD")
        parser.add_argument('end_date', help="YYYY-MM-DD")

    def handle(self, domain, indicator_config_id, start_date, end_date, **options):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)

        form_ids = get_form_ids_by_type(
            domain=domain,
            type_='XFormInstance',
            start=start_date,
            end=end_date,
        )
        rebuild_indicators_in_place(indicator_config_id, None, form_ids)
