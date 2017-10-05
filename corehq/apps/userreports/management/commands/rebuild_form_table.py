from __future__ import print_function
from datetime import datetime
import argparse

from django.core.management.base import BaseCommand

from corehq.apps.es import forms as form_es
from corehq.apps.userreports.tasks import rebuild_indicators_in_place


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
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        time_filter = form_es.submitted
        query = (form_es.FormES()
                 .domain(domain)
                 .filter(time_filter(gte=start_date, lte=end_date)))
        if xmlns_list:
            query = query.OR(*[form_es.xmlns(x) for x in xmlns_list])

        form_ids = IterableESID(query)
        rebuild_indicators_in_place.delay(indicator_config_id, None, form_ids)


class IterableESID():
    def __init__(self, query):
        self.query = query
        self.query_result = None
        self.index = 0

    def __iter__(self):
        return self

    def next(self):
        if not self.query_result:
            self.query_result = self.query.get_ids()
        id = self.query_result[self.index]
        self.index += 1
        return id
