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
        session = session_helper.Session
        buckets = [('0 months', '6 months'),
                   ('6 months', '2 years'),
                   ('2 years', '6 years'),
                   ('6 years', '14 years'),
                   ('14 years', '18 years')
                   ]
        # 200 because we need 18+  and person of age more than 200 is not expected
        buckets.append(('18 years', '200 years'))
        with open(
            os.path.join(os.path.dirname(__file__), 'sql_scripts', 'nos_of_deaths.sql'),
            encoding='utf-8'
        ) as f:
            sql_script = f.read()
            for bucket in buckets:
                rows = session.execute(
                        sql_script % {
                        'person_table_name': person_table_name,
                        'from_age': bucket[0],
                        'to_age': bucket[1]
                        }
                        )
                f_path = file_path + os.sep + bucket[0].replace(' ', '_') + bucket[1].replace(' ', '_') + '.csv'
                with open(f_path, 'w', encoding='utf-8') as file_object:
                        writer = csv.writer(file_object)
                        writer.writerow([
                        'State',
                        'District',
                        'AWC',
                        'Month',
                        'Deaths',
                        ])
                        writer.writerows(rows)
