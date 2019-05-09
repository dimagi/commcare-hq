from __future__ import absolute_import, print_function

from __future__ import unicode_literals
from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from sqlalchemy import select

from corehq.apps.userreports.models import get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter


class Command(BaseCommand):
    help = "Migrate data from one UCR to another"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('old_data_source_id')
        parser.add_argument('new_data_source_id')
        parser.add_argument('--date-column', default='inserted_at')
        parser.add_argument('--initiated-by', action='store', required=True, dest='initiated',
                            help='Who initiated the rebuild')

    def handle(self, domain, old_data_source_id, new_data_source_id, **options):
        old_config, _ = get_datasource_config(old_data_source_id, domain)
        new_config, _ = get_datasource_config(new_data_source_id, domain)

        assert old_config.referenced_doc_type == new_config.referenced_doc_type
        old_filter = old_config.get_case_type_or_xmlns_filter()
        new_filter = new_config.get_case_type_or_xmlns_filter()
        assert set(old_filter) == set(new_filter)

        old_adapter = get_indicator_adapter(old_config)
        new_adapter = get_indicator_adapter(new_config)

        old_table = old_adapter.get_table()
        new_table = new_adapter.get_table()

        assert hasattr(old_table.columns, options['date_column'])

        column = getattr(old_table.columns, options['date_column'])

        new_adapter.build_table(initiated_by=options['initiated'], source='migrate_ucr')

        end_date = date(2016, 1, 1)
        query = self.insert_query(old_table, new_table, column, end_date=end_date)
        self.run_query(new_adapter, query)

        start_date = end_date
        end_date = end_date + relativedelta(months=1)
        while start_date < date.today():
            query = self.insert_query(old_table, new_table, column, start_date, end_date)
            self.run_query(new_adapter, query)
            start_date += relativedelta(months=1)
            end_date += relativedelta(months=1)

        query = self.insert_query(old_table, new_table, column, start_date)
        self.run_query(new_adapter, query)

    def insert_query(self, old_table, new_table, column, start_date=None, end_date=None):
        if start_date is None:
            where_query = (column < end_date)
        elif end_date is None:
            where_query = (column >= start_date)
        else:
            where_query = (column >= start_date) & (column < end_date)

        sel = select(old_table.c).where(where_query)
        return new_table.insert().from_select(new_table.c, sel)

    def run_query(self, adapter, query):
        print(query)
        print(datetime.utcnow())
        with adapter.engine.begin() as connection:
            connection.execute(query)
        print("query complete")
