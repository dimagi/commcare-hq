from __future__ import print_function
from datetime import datetime

from django.core.management.base import BaseCommand


from corehq.apps.es import forms as form_es
from corehq.apps.userreports.tasks import rebuild_indicators_in_place

class Command(BaseCommand):
    help = "Rebuild a table in place for forms in a specific time period"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('start_date', help="YYYY-MM-DD")
        parser.add_argument('end_date', help="YYYY-MM-DD")
        parser.add_argument('indicator_config_id')

    def handle(self, domain, start_date, end_date, indicator_config_id, **options):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        time_filter = form_es.submitted
        form_ids = (form_es.FormES()
                    .domain(domain)
                    .filter(time_filter(gte=start_date, lte=end_date))
                    .get_ids())
        rebuild_indicators_in_place(indicator_config_id, None, form_ids)
