import inspect
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

import attr
import dateutil

from dimagi.utils.chunked import chunked

from corehq.apps.hqadmin.management.commands.stale_data_in_es import (
    get_sql_case_data_for_db,
)
from corehq.apps.userreports.util import get_table_name
from corehq.form_processor.models import XFormInstanceSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


@attr.s
class RunConfig(object):
    domain = attr.ib()
    table_id = attr.ib()
    start_date = attr.ib()
    end_date = attr.ib()
    case_type = attr.ib()
    xmlns = attr.ib()

    @property
    def run_with_forms(self):
        return bool(self.xmlns)


class Command(BaseCommand):
    """
    Returns list of (doc_id, doc_type, doc_subtype, ucr_insert_on, modified_on)
    tuples for all cases or forms that are not found in the specified UCR.

    Can be used in conjunction with republish_doc_changes

        1. Generate tuples not updated in the UCR data source with extra debug columns
        $ ./manage.py stale_data_in_ucr <DOMAIN> <table_id> --xmlns <xmlns> --start 2019-09-19 --end 2019-09-28 > stale_ids.txt

        2. Republish case changes
        $ ./manage.py republish_doc_changes <DOMAIN> stale_ids.txt
    """
    help = inspect.cleandoc(__doc__).split('\n')[0]

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('table_id')
        parser.add_argument(
            '--case-type',
            action='store',
            help='Mutually exclusive with XMLNS',
        )
        parser.add_argument(
            '--xmlns',
            action='store',
            help='Mutually exclusive with case_type',
        )
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

    def handle(self, domain, table_id, **options):
        if options['case_type'] and options['xmlns']:
            raise CommandError('You may only specify one of case_type or XMLNS')

        start = dateutil.parser.parse(options['start']) if options['start'] else datetime(2010, 1, 1)
        end = dateutil.parser.parse(options['end']) if options['end'] else datetime.utcnow()

        run_config = RunConfig(domain, table_id, start, end, options['case_type'], options['xmlns'])
        if not should_use_sql_backend(run_config.domain):
            raise CommandError('This command only supports SQL domains.')

        for doc_id, doc_type, ucr_date, primary_date in _get_stale_data(run_config):
            print(f"{doc_id},{doc_type},{ucr_date},{primary_date}")


def _get_stale_data(run_config):
    for db in get_db_aliases_for_partitioned_query():
        print(f"Starting db {db}")
        matching_records_for_db = _get_primary_data_for_db(db, run_config)
        chunk_size = 1000
        for chunk in chunked(matching_records_for_db, chunk_size):
            doc_ids = [val[0] for val in chunk]
            ucr_insertion_dates = _get_ucr_insertion_dates(run_config.domain, run_config.table_id, doc_ids)
            for doc_id, doc_type, sql_modified_on in chunk:
                ucr_insert_date = ucr_insertion_dates.get(doc_id)
                if (not ucr_insert_date
                        # Handle small time drift between databases
                        or (sql_modified_on - ucr_insert_date) < timedelta(seconds=1)):
                    ucr_date_string = ucr_insert_date.isoformat() if ucr_insert_date else ''
                    yield (doc_id, doc_type, ucr_date_string, sql_modified_on.isoformat())


def _get_ucr_insertion_dates(domain, table_id, doc_ids):
    table_name = get_table_name(domain, table_id)
    with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
        query = f'''
            SELECT
                doc_id,
                inserted_at
            FROM "{table_name}"
            WHERE doc_id = ANY(%(doc_ids)s);
        '''
        cursor.execute(query, {'doc_ids': doc_ids})
        return dict(cursor.fetchall())


def _get_primary_data_for_db(db, run_config):
    if run_config.run_with_forms:
        matching_xforms = XFormInstanceSQL.objects.using(db).filter(
            domain=run_config.domain,
            received_on__gte=run_config.start_date,
            received_on__lte=run_config.end_date,
            state=XFormInstanceSQL.NORMAL,
        )
        if run_config.xmlns:
            matching_xforms = matching_xforms.filter(xmlns=run_config.xmlns)
        return matching_xforms.values_list('form_id', 'xmlns', 'received_on')
    else:
        return get_sql_case_data_for_db(db, run_config)
