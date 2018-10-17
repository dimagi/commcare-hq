from __future__ import absolute_import, print_function

from __future__ import unicode_literals
import csv342 as csv
import os

from django.core.management.base import BaseCommand

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name

from corehq.sql_db.connections import connection_manager
from io import open

PERSON_TABLE_ID = 'static-person_cases_v2'
AWC_LOCATION_TABLE_ID = 'static-awc_location'


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path'
        )

    def handle(self, file_path, *args, **options):
        domain = 'icds-cas'

        data_source_id = StaticDataSourceConfiguration.get_doc_id(domain, PERSON_TABLE_ID)
        config = StaticDataSourceConfiguration.by_id(data_source_id)
        adapter = get_indicator_adapter(config)
        session_helper = connection_manager.get_session_helper(adapter.engine_id)
        person_table_name = get_table_name(domain, PERSON_TABLE_ID)
        awc_location_table_name = get_table_name(domain, AWC_LOCATION_TABLE_ID)
        session = session_helper.Session

        with open(
            os.path.join(os.path.dirname(__file__), 'sql_scripts', 'nos_of_deaths.sql'),
            encoding='utf-8'
        ) as f:
            sql_script = f.read()
            rows = session.execute(
                sql_script % {
                    'person_table_name': person_table_name,
                    'awc_location_table_name': awc_location_table_name
                }
            )

            with open(file_path, 'w', encoding='utf-8') as file_object:
                writer = csv.writer(file_object)
                writer.writerow([
                    'State',
                    'District',
                    'AWC',
                    'Month',
                    'Deaths',
                ])
                writer.writerows(rows)
