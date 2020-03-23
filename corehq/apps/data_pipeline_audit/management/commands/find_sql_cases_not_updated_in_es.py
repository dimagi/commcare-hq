from collections import namedtuple

from django.core.management.base import BaseCommand

from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor, \
    iter_all_ids_chunked, CaseAccessorSQL
from corehq.form_processor.change_publishers import publish_case_saved
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.argparse_types import date_type

from corehq.apps.es import CaseES
from corehq.form_processor.models import CommCareCaseSQL
from corehq.util.dates import iso_string_to_datetime


class Command(BaseCommand):
    help = "Print IDs and info of sql cases whose server_modified_on is wrong in ES."

    def add_arguments(self, parser):
        parser.add_argument(
            '-d',
            '--domain',
            dest='domain',
            help="Filter by this domain (optional)",
        )
        parser.add_argument(
            '-s',
            '--startdate',
            dest='start',
            type=date_type,
            help="The start date. Only applicable to case on SQL domains. - format YYYY-MM-DD",
        )
        parser.add_argument(
            '-e',
            '--enddate',
            dest='end',
            type=date_type,
            help="The end date. Only applicable to case on SQL domains. - format YYYY-MM-DD",
        )
        parser.add_argument(
            '--fix',
            dest='fix',
            action='store_true',
            help="Whether to fix by republishing to kafka.",
            default=False,
        )

    def handle(self, **options):
        domain = options.get('domain')
        startdate = options.get('start')
        enddate = options.get('end')
        fix = options.get('fix')

        chunked_case_ids = get_case_ids_chunked(
            domain=domain, start_date=startdate, end_date=enddate)

        print('Case ID\tLast Modified\tDomain')
        for case_ids_chunk in chunked_case_ids:
            es_modified_set = get_es_id_modified_list(domain, case_ids_chunk)

            sql_modified_set = get_sql_id_modified_list(domain, case_ids_chunk)
            bad_set = sql_modified_set - es_modified_set
            for info in bad_set:
                print(f'{info.case_id}\t{info.server_modified_on}\t{info.domain}')
            if fix:
                for case in CaseAccessorSQL.get_cases([info.case_id for info in bad_set]):
                    publish_case_saved(case, send_post_save_signal=False)


def get_case_ids_chunked(domain=None, start_date=None, end_date=None):
    reindex_accessor = CaseReindexAccessor(
        domain=domain, start_date=start_date, end_date=end_date)
    yield from iter_all_ids_chunked(reindex_accessor)


def get_es_id_modified_list(domain, case_ids):
    es_query = CaseES()
    if domain:
        es_query = es_query.domain(domain)
    return {
        CaseResult(case_id, iso_string_to_datetime(server_modified_on), domain_)
        for case_id, server_modified_on, domain_ in (
            es_query.case_ids(case_ids).values_list('_id', 'server_modified_on', 'domain'))
    }


def get_sql_id_modified_list(domain, case_ids):
    q_kwargs = {}
    if domain:
        q_kwargs['domain'] = domain
    return {
        CaseResult(case_id, server_modified_on, domain_)
        for result in (
            (CommCareCaseSQL.objects.using(db_alias)
             .filter(case_id__in=case_ids, **q_kwargs)
             .values_list('case_id', 'server_modified_on', 'domain'))
            for db_alias in get_db_aliases_for_partitioned_query()
        )
        for case_id, server_modified_on, domain_ in result
    }


CaseResult = namedtuple('CaseResult', 'case_id, server_modified_on, domain')
