import inspect
import sys
from collections import namedtuple
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

import dateutil

from casexml.apps.case.models import CommCareCase
from dimagi.utils.chunked import chunked

from corehq.apps.es import CaseES, FormES
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.form_processor.backends.sql.dbaccessors import state_to_doc_type
from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.couch_helpers import paginate_view
from corehq.util.dates import iso_string_to_datetime
from corehq.util.log import with_progress_bar

RunConfig = namedtuple('RunConfig', ['domain', 'start_date', 'end_date', 'case_type'])
DataRow = namedtuple('DataRow', ['doc_id', 'doc_type', 'doc_subtype', 'domain', 'es_date', 'primary_date'])


ALL_SQL_DOMAINS = object()
HEADER_ROW = DataRow(
    doc_id='Doc ID',
    doc_type='Doc Type',
    doc_subtype='Doc Subtype',
    domain='Domain',
    es_date='ES Date',
    primary_date='Correct Date',
)


class Command(BaseCommand):
    """
    Returns list of (doc_id, doc_type, doc_subtype, es_server_modified_on, primary_modified_on)
    tuples that are not updated in ES. Works for cases and forms.

    Can be used in conjunction with republish_doc_changes

        1. Generate tuples not updated in ES with extra debug columns
        $ ./manage.py stale_data_in_es case form --domain DOMAIN > stale_ids.csv

        (Can call with just "case" or "form" if only want to use one data model type)

        2. Republish doc changes
        $ ./manage.py republish_doc_changes <DOMAIN> stale_ids.csv
    """
    help = inspect.cleandoc(__doc__).split('\n')[0]

    def add_arguments(self, parser):
        parser.add_argument('data_models', nargs='+',
                            help='A list of data models to check. Valid options are "case" and "form".')
        parser.add_argument('--domain', default=ALL_SQL_DOMAINS)
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
        parser.add_argument(
            '--case_type',
            action='store',
            help='Only run for the specified case type',
        )

    def handle(self, domain, data_models, **options):
        data_models = set(data_models)

        start = dateutil.parser.parse(options['start']) if options['start'] else datetime(2010, 1, 1)
        end = dateutil.parser.parse(options['end']) if options['end'] else datetime.utcnow()
        case_type = options['case_type']
        run_config = RunConfig(domain, start, end, case_type)

        if run_config.domain is ALL_SQL_DOMAINS:
            print('Running for all SQL domains (and excluding Couch domains!)', file=sys.stderr)

        self.print_data_row(HEADER_ROW)

        for data_model in data_models:
            try:
                process_data_model_fn = DATA_MODEL_BACKENDS[data_model.lower()]()
            except KeyError:
                raise CommandError('Only valid options for data model are "{}"'.format(
                    '", "'.join(DATA_MODEL_BACKENDS.keys())
                ))
            data_rows = process_data_model_fn(run_config)

            for data_row in data_rows:
                self.print_data_row(data_row)

    @staticmethod
    def print_data_row(data_row):
        print(','.join(data_row))


DATA_MODEL_BACKENDS = {
    'case': lambda: CaseBackend.run,
    'form': lambda: FormBackend.run,
}


class CaseBackend:
    @staticmethod
    def run(run_config):
        rows = CaseBackend._get_server_modified_on_for_domain(run_config)
        for case_id, case_type, es_date, primary_date, domain in rows:
            yield DataRow(doc_id=case_id, doc_type='CommCareCase', doc_subtype=case_type, domain=domain,
                          es_date=es_date or 'None', primary_date=primary_date)

    @staticmethod
    def _get_server_modified_on_for_domain(run_config):
        if run_config.domain is ALL_SQL_DOMAINS or should_use_sql_backend(run_config.domain):
            return CaseBackend._get_data_for_sql_backend(run_config)
        else:
            return CaseBackend._get_data_for_couch_backend(run_config)

    @staticmethod
    def _get_data_for_sql_backend(run_config):
        for db in get_db_aliases_for_partitioned_query():
            matching_records_for_db = get_sql_case_data_for_db(db, run_config)
            chunk_size = 1000
            for chunk in chunked(matching_records_for_db, chunk_size):
                case_ids = [val[0] for val in chunk]
                es_modified_on_by_ids = CaseBackend._get_es_modified_dates(run_config.domain, case_ids)
                for case_id, case_type, sql_modified_on, domain in chunk:
                    sql_modified_on_str = f'{sql_modified_on.isoformat()}Z'
                    es_modified_on = es_modified_on_by_ids.get(case_id)
                    if not es_modified_on or (es_modified_on < sql_modified_on_str):
                        yield case_id, case_type, es_modified_on, sql_modified_on_str, domain

    @staticmethod
    def _get_data_for_couch_backend(run_config):
        if run_config.case_type:
            raise CommandError('Case type argument is not supported for couch domains!')
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
            es_modified_on_by_ids = CaseBackend._get_es_modified_dates(domain, case_ids)
            for row in chunk:
                case_id, couch_modified_on = row['id'], row['value']
                if iso_string_to_datetime(couch_modified_on) > start_time:
                    # skip cases modified after the script started
                    continue
                es_modified_on = es_modified_on_by_ids.get(case_id)
                if not es_modified_on or (es_modified_on != couch_modified_on):
                    yield case_id, 'COUCH_TYPE_NOT_SUPPORTED', es_modified_on, couch_modified_on, run_config.domain

    @staticmethod
    def _get_es_modified_dates(domain, case_ids):
        es_query = CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
        if domain is not ALL_SQL_DOMAINS:
            es_query = es_query.domain(domain)
        results = es_query.case_ids(case_ids).values_list('_id', 'server_modified_on')
        return dict(results)


def get_sql_case_data_for_db(db, run_config):
    matching_cases = CommCareCaseSQL.objects.using(db).filter(
        server_modified_on__gte=run_config.start_date,
        server_modified_on__lte=run_config.end_date,
        deleted=False,
    )
    if run_config.domain is not ALL_SQL_DOMAINS:
        matching_cases = matching_cases.filter(
            domain=run_config.domain,
        )
    if run_config.case_type:
        matching_cases = matching_cases.filter(
            type=run_config.case_type
        )
    return matching_cases.values_list('case_id', 'type', 'server_modified_on', 'domain')


class FormBackend:
    @staticmethod
    def run(run_config):
        rows = FormBackend._get_stale_form_data(run_config)
        for form_id, doc_type, xmlns, es_date, primary_date, domain in rows:
            yield DataRow(doc_id=form_id, doc_type=doc_type, doc_subtype=xmlns, domain=domain,
                          es_date=es_date or 'None', primary_date=primary_date)

    @staticmethod
    def _get_stale_form_data(run_config):
        if run_config.domain is ALL_SQL_DOMAINS or should_use_sql_backend(run_config.domain):
            return FormBackend._get_stale_form_data_for_sql_backend(run_config)
        else:
            raise CommandError('Form data for couch domains is not supported!')

    @staticmethod
    def _get_stale_form_data_for_sql_backend(run_config):
        for db in get_db_aliases_for_partitioned_query():
            matching_records_for_db = FormBackend._get_sql_form_data_for_db(db, run_config)
            chunk_size = 1000
            length = len(matching_records_for_db) // chunk_size
            chunk_iter = chunked(matching_records_for_db, chunk_size)
            for chunk in with_progress_bar(chunk_iter, prefix=f'Processing DB {db}',
                                           length=length, stream=sys.stderr):
                form_ids = [val[0] for val in chunk]
                es_modified_on_by_ids = FormBackend._get_es_modified_dates_for_forms(run_config.domain, form_ids)
                for form_id, state, xmlns, sql_modified_on, domain in chunk:
                    doc_type = state_to_doc_type.get(state, 'XFormInstance')
                    sql_modified_on_str = f'{sql_modified_on.isoformat()}Z'
                    es_modified_on = es_modified_on_by_ids.get(form_id)
                    if not es_modified_on or (es_modified_on < sql_modified_on_str):
                        yield form_id, doc_type, xmlns, es_modified_on, sql_modified_on_str, domain

    @staticmethod
    def _get_sql_form_data_for_db(db, run_config):
        matching_forms = XFormInstanceSQL.objects.using(db).filter(
            received_on__gte=run_config.start_date,
            received_on__lte=run_config.end_date,
        )
        if run_config.domain is not ALL_SQL_DOMAINS:
            matching_forms = matching_forms.filter(
                domain=run_config.domain
            )
        return matching_forms.values_list('form_id', 'state', 'xmlns', 'received_on', 'domain')

    @staticmethod
    def _get_es_modified_dates_for_forms(domain, form_ids):
        es_query = FormES(es_instance_alias=ES_EXPORT_INSTANCE).remove_default_filters()
        if domain is not ALL_SQL_DOMAINS:
            es_query = es_query.domain(domain)
        results = es_query.form_ids(form_ids).values_list('_id', 'received_on')
        return dict(results)
