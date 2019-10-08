
import inspect
from collections import namedtuple

import dateutil
from django.core.management.base import BaseCommand, CommandError
from datetime import datetime

from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from dimagi.utils.chunked import chunked

from casexml.apps.case.models import CommCareCase
from corehq.apps.es import CaseES, FormES
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.util.dates import iso_string_to_datetime
from corehq.util.couch_helpers import paginate_view



RunConfig = namedtuple('RunConfig', ['domain', 'start_date', 'end_date'])


class Command(BaseCommand):
    """
    Returns list of (doc_id, doc_type, doc_subtype, es_server_modified_on, couch_server_modified_on)
    tuples that are not updated in ES. Works for cases and forms.

    Can be used in conjunction with republish_doc_changes

        1. Generate tuples not updated in ES with extra debug columns
        $ ./manage.py stale_data_in_es <DOMAIN> case form > stale_ids.txt

        (Can call with just "case" or "form" if only want to use one data model type)

        2. Republish case changes
        $ ./manage.py republish_doc_changes <DOMAIN> stale_ids.txt
    """
    help = inspect.cleandoc(__doc__).split('\n')[0]

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('data_models', nargs='+',
                            help='A list of data models to check. Valid options are "case"')
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

    def handle(self, domain, data_models, **options):
        data_models = set(data_models)

        start = dateutil.parser.parse(options['start']) if options['start'] else datetime(2010, 1, 1)
        end = dateutil.parser.parse(options['end']) if options['end'] else datetime.utcnow()
        run_config = RunConfig(domain, start, end)

        for data_model in data_models:
            if data_model.lower() == 'case':
                for case_id, case_type, es_date, primary_date in get_server_modified_on_for_domain(run_config):
                    print(f"{case_id},CommCareCase,{case_type},{es_date},{primary_date}")
            elif data_model.lower() == 'form':
                for form_id, xmlns, es_date, primary_date in get_stale_form_data(run_config):
                    print(f"{form_id},XFormInstance,{xmlns},{es_date},{primary_date}")
            else:
                raise CommandError('Only valid options for data model are "case" and "form"')


def get_server_modified_on_for_domain(run_config):
    if should_use_sql_backend(run_config.domain):
        return _get_data_for_sql_backend(run_config)
    else:
        return _get_data_for_couch_backend(run_config)


def _get_data_for_couch_backend(run_config):
    domain = run_config.domain
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
        es_modified_on_by_ids = _get_es_modified_dates(domain, case_ids)
        for row in chunk:
            case_id, couch_modified_on = row['id'], row['value']
            if iso_string_to_datetime(couch_modified_on) > start_time:
                # skip cases modified after the script started
                continue
            es_modified_on = es_modified_on_by_ids.get(case_id)
            if not es_modified_on or (es_modified_on != couch_modified_on):
                yield (case_id, 'COUCH_TYPE_NOT_SUPPORTED', es_modified_on, couch_modified_on)


def _get_data_for_sql_backend(run_config):
    for db in get_db_aliases_for_partitioned_query():
        matching_records_for_db = _get_sql_case_data_for_db(db, run_config)
        chunk_size = 1000
        for chunk in chunked(matching_records_for_db, chunk_size):
            case_ids = [val[0] for val in chunk]
            es_modified_on_by_ids = _get_es_modified_dates(run_config.domain, case_ids)
            for case_id, case_type, sql_modified_on in chunk:
                sql_modified_on_str = f'{sql_modified_on.isoformat()}Z'
                es_modified_on = es_modified_on_by_ids.get(case_id)
                if not es_modified_on or (es_modified_on < sql_modified_on_str):
                    yield (case_id, case_type, es_modified_on, sql_modified_on_str)


def _get_sql_case_data_for_db(db, run_config):
    return CommCareCaseSQL.objects.using(db).filter(
        domain=run_config.domain,
        server_modified_on__gte=run_config.start_date,
        server_modified_on__lte=run_config.end_date,
    ).values_list('case_id', 'type', 'server_modified_on')


def _get_es_modified_dates(domain, case_ids):
    results = (CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain)
            .case_ids(case_ids)
            .values_list('_id', 'server_modified_on'))
    return dict(results)


def get_stale_form_data(run_config):
    if should_use_sql_backend(run_config.domain):
        return _get_stale_form_data_for_sql_backend(run_config)
    else:
        raise CommandError('Form data for couch domains is not supported!')


def _get_stale_form_data_for_sql_backend(run_config):
    for db in get_db_aliases_for_partitioned_query():
        matching_records_for_db = _get_sql_form_data_for_db(db, run_config)
        chunk_size = 1000
        for chunk in chunked(matching_records_for_db, chunk_size):
            form_ids = [val[0] for val in chunk]
            es_modified_on_by_ids = _get_es_modified_dates_for_forms(run_config.domain, form_ids)
            for form_id, xmlns, sql_modified_on in chunk:
                sql_modified_on_str = f'{sql_modified_on.isoformat()}Z'
                es_modified_on = es_modified_on_by_ids.get(form_id)
                if not es_modified_on or (es_modified_on < sql_modified_on_str):
                    yield (form_id, xmlns, es_modified_on, sql_modified_on_str)


def _get_sql_form_data_for_db(db, run_config):
    return XFormInstanceSQL.objects.using(db).filter(
        domain=run_config.domain,
        received_on__gte=run_config.start_date,
        received_on__lte=run_config.end_date,
    ).values_list('form_id', 'xmlns', 'received_on')


def _get_es_modified_dates_for_forms(domain, form_ids):
    results = (FormES(es_instance_alias=ES_EXPORT_INSTANCE)
        .domain(domain)
        .form_ids(form_ids)
        .values_list('_id', 'received_on'))
    return dict(results)
