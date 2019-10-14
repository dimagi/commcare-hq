
import inspect

import dateutil
from django.core.management.base import BaseCommand, CommandError
from datetime import datetime

from corehq.apps.hqadmin.management.commands.stale_data_in_es import RunConfig, get_sql_case_data_for_db
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from corehq.form_processor.utils import should_use_sql_backend
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from custom.icds_reports.models.aggregate import get_cursor, AggAwc
from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    """
    Returns list of (doc_id, doc_type, doc_subtype, ucr_insert_on, modified_on)
    tuples for all househould cases that are not found static-household_cases UCR.

    Can be used in conjunction with republish_doc_changes

        1. Generate tuples not updated in ES with extra debug columns
        $ ./manage.py stale_data_in_househould_ucr <DOMAIN> --start 2019-09-19 --end 2019-09-28 > stale_ids.txt

        2. Republish case changes
        $ ./manage.py republish_doc_changes <DOMAIN> stale_ids.txt
    """
    help = inspect.cleandoc(__doc__).split('\n')[0]

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--start',
            action='store',
            help='Only include data modified after this date',
        )
        parser.add_argument(
            '--end',
            action='store',
            help='Only include data modified before this date',
        )

    def handle(self, domain, **options):
        start = dateutil.parser.parse(options['start']) if options['start'] else datetime(2010, 1, 1)
        end = dateutil.parser.parse(options['end']) if options['end'] else datetime.utcnow()
        run_config = RunConfig(domain, start, end, 'household')
        if not should_use_sql_backend(run_config.domain):
            raise CommandError('This command only supports SQL domains.')
        for case_id, case_type, ucr_date, primary_date in _get_stale_data(run_config):
            print(f"{case_id},CommCareCase,{case_type},{ucr_date},{primary_date}")


def _get_stale_data(run_config):
    for db in get_db_aliases_for_partitioned_query():
        matching_records_for_db = get_sql_case_data_for_db(db, run_config)
        chunk_size = 1000
        for chunk in chunked(matching_records_for_db, chunk_size):
            case_ids = [val[0] for val in chunk]
            ucr_insertion_dates = _get_ucr_insertion_dates(run_config.domain, case_ids)
            for case_id, case_type, sql_modified_on in chunk:
                ucr_insert_date = ucr_insertion_dates.get(case_id)
                if not ucr_insert_date or (ucr_insert_date < sql_modified_on):
                    ucr_date_string = ucr_insert_date.isoformat() if ucr_insert_date else ''
                    yield (case_id, case_type, ucr_date_string, sql_modified_on.isoformat())


def _get_ucr_insertion_dates(domain, case_ids):
    ucr_id = StaticDataSourceConfiguration.get_doc_id(domain, 'static-household_cases')
    config, _ = get_datasource_config(ucr_id, domain)
    table_name = get_table_name(domain, config.table_id)
    with get_cursor(AggAwc) as cursor:
        query = f'''
            SELECT
                doc_id,
                inserted_at
            FROM "{table_name}"
            WHERE doc_id = ANY(%(case_ids)s);
        '''
        cursor.execute(query, {'case_ids': case_ids})
        return dict(cursor.fetchall())
