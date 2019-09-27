
import inspect

from django.core.management.base import BaseCommand
from datetime import datetime

from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from dimagi.utils.chunked import chunked

from casexml.apps.case.models import CommCareCase
from corehq.apps.es import CaseES
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.util.dates import iso_string_to_datetime
from corehq.util.couch_helpers import paginate_view


class Command(BaseCommand):
    """
    Returns list of (case_id, es_server_modified_on, couch_server_modified_on)
        tuples that are not updated in ES

        Can be used in conjunction with republish_couch_case_changes

        1. Generate couch case tuples not updated in ES with extra debug columns
        $ ./manage.py stale_cases_in_es <DOMAIN> > case_ids_info.txt

        2. Strip debug columns to prepare for reprocessing
        $ cut -d, -f2-3 --complement case_ids_info.txt > case_ids.txt

        3. Republish case changes
        $ ./manage.py republish_couch_case_changes <DOMAIN> case_ids.txt

    """
    help = inspect.cleandoc(__doc__).split('\n')[0]

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        for case_id, es_date, couch_date in get_server_modified_on_for_domain(domain):
            print("{id},{es_date},{couch_date}".format(
                id=case_id,
                es_date=es_date or "",
                couch_date=couch_date
            ))


def get_server_modified_on_for_domain(domain):
    if should_use_sql_backend(domain):
        return _get_data_for_sql_backend(domain)
    else:
        return _get_data_for_couch_backend(domain)


def _get_data_for_couch_backend(domain):
    start_time = datetime.utcnow()
    chunk_size = 1000
    chunked_iterator = chunked(paginate_view(
        CommCareCase.get_db(),
        'cases_by_server_date/by_server_modified_on',
        chunk_size=chunk_size,
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        reduce=False
    ), chunk_size)
    for chunk in chunked_iterator:
        case_ids = [row['id'] for row in chunk]
        results = (CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain)
            .case_ids(case_ids)
            .values_list('_id', 'server_modified_on'))
        es_modified_on_by_ids = dict(results)
        for row in chunk:
            case_id, couch_modified_on = row['id'], row['value']
            if iso_string_to_datetime(couch_modified_on) > start_time:
                # skip cases modified after the script started
                continue
            es_modified_on = es_modified_on_by_ids.get(case_id)
            if not es_modified_on or (es_modified_on != couch_modified_on):
                yield (case_id, es_modified_on, couch_modified_on)


def _get_data_for_sql_backend(domain):

    for db in get_db_aliases_for_partitioned_query():
        matching_records_for_db = _get_sql_case_data_for_db(db, domain)
        chunk_size = 1000
        for chunk in chunked(matching_records_for_db, chunk_size):
            case_ids = [val[0] for val in chunk]
            # case_ids = list(chunk)
            results = (CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
                .domain(domain)
                .case_ids(case_ids)
                .values_list('_id', 'server_modified_on'))
            es_modified_on_by_ids = dict(results)
            for case_id, sql_modified_on in chunk:
                sql_modified_on_str = f'{sql_modified_on.isoformat()}Z'
                es_modified_on = es_modified_on_by_ids.get(case_id)
                if not es_modified_on or (es_modified_on != sql_modified_on_str):
                    yield (case_id, es_modified_on, sql_modified_on_str)


def _get_sql_case_data_for_db(db, domain):
    # todo: parameterize these
    start_date = datetime(2010, 1, 1)
    end_date = datetime.utcnow()
    yield from CommCareCaseSQL.objects.using(db).filter(
        domain=domain,
        server_modified_on__gte=start_date,
        server_modified_on__lte=end_date,
    ).values_list('case_id', 'server_modified_on')
