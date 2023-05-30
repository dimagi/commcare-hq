import csv
import inspect
import sys
from collections import namedtuple
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

import dateutil

from dimagi.utils.chunked import chunked
from dimagi.utils.retry import retry_on

from corehq.apps.es import CaseES, CaseSearchES, FormES
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseReindexAccessor,
    FormReindexAccessor,
)
from corehq.form_processor.models import CommCareCase
from corehq.pillows.case_search import domain_needs_search_index
from corehq.util.dates import iso_string_to_datetime
from corehq.util.doc_processor.progress import (
    ProcessorProgressLogger,
    ProgressManager,
)
from corehq.util.doc_processor.sql import resumable_sql_model_iterator
from corehq.elastic import ESError


CHUNK_SIZE = 1000

RunConfig = namedtuple('RunConfig', ['iteration_key', 'domain', 'start_date', 'end_date', 'case_type'])
DataRow = namedtuple('DataRow', ['doc_id', 'doc_type', 'doc_subtype', 'domain', 'es_date', 'primary_date'])


ALL_DOMAINS = object()
HEADER_ROW = DataRow(
    doc_id='Doc ID',
    doc_type='Doc Type',
    doc_subtype='Doc Subtype',
    domain='Domain',
    es_date='ES Date',
    primary_date='Correct Date',
)


def get_csv_args(delimiter):
    return {
        'delimiter': delimiter,
        'lineterminator': '\n',
    }


retry_on_es_timeout = retry_on(ESError, delays=[2**x for x in range(10)])


class Command(BaseCommand):
    """
    Returns list of (doc_id, doc_type, doc_subtype, es_server_modified_on, primary_modified_on)
    tuples that are not updated in ES. Works for cases and forms.

    Can be used in conjunction with republish_doc_changes

        1. Generate tuples not updated in ES with extra debug columns
        $ ./manage.py stale_data_in_es case form --domain DOMAIN > stale_ids.tsv

        (Can call with just "case" or "form" if only want to use one data model type)

        2. Republish doc changes
        $ ./manage.py republish_doc_changes stale_ids.tsv
    """
    help = inspect.cleandoc(__doc__).split('\n')[0]

    def add_arguments(self, parser):
        parser.add_argument('data_models', nargs='+',
                            help='A list of data models to check. Valid options are "case" and "form".')
        parser.add_argument('--domain', default=ALL_DOMAINS)
        parser.add_argument('--iteration_key', help='Unique slug to identify this run. Used to allow resuming.')
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
        parser.add_argument('--delimiter', default='\t', choices=('\t', ','))

    def handle(self, domain, data_models, delimiter, **options):
        data_models = set(data_models)

        default_start, default_end = datetime(2010, 1, 1), datetime.utcnow()
        start = dateutil.parser.parse(options['start']) if options['start'] else default_start
        end = dateutil.parser.parse(options['end']) if options['end'] else default_end
        case_type = options['case_type']
        iteration_key = options['iteration_key']
        if iteration_key:
            print(f'\nResuming previous run. Iteration Key:\n\t"{iteration_key}"\n', file=self.stderr)
        else:
            iteration_key = (
                f'stale_data_{datetime.utcnow().isoformat()}'
                f'-{"" if domain == ALL_DOMAINS else domain}'
                f'-{start.isoformat() if start != default_start else ""}'
                f'-{end.isoformat() if end != default_end else ""}'
                f'-{case_type or ""}'
            )
            print(f'\nStarting new run. Iteration key:\n\t"{iteration_key}"\n', file=self.stderr)

        run_config = RunConfig(iteration_key, domain, start, end, case_type)

        if run_config.domain is ALL_DOMAINS:
            print('Running for all domains', file=self.stderr)

        csv_writer = csv.writer(self.stdout, **get_csv_args(delimiter))

        def print_data_row(data_row):
            # Casting as str print `None` as 'None'
            csv_writer.writerow(map(str, data_row))

        print_data_row(HEADER_ROW)

        try:
            for data_model in data_models:
                try:
                    process_data_model_fn = DATA_MODEL_HELPERS[data_model.lower()]()
                except KeyError:
                    raise CommandError('Only valid options for data model are "{}"'.format(
                        '", "'.join(DATA_MODEL_HELPERS.keys())
                    ))
                data_rows = process_data_model_fn(run_config)

                for data_row in data_rows:
                    print_data_row(data_row)
        except:  # noqa: E722
            print(f'\nERROR: To resume the previous run add the "iteration_key" parameter to the command:\n'
                  f"\t--iteration_key '{iteration_key}'\n", file=self.stderr)
            raise


DATA_MODEL_HELPERS = {
    'case': lambda: CaseHelper.run,
    'form': lambda: FormHelper.run,
}


class CaseHelper:

    @classmethod
    def run(cls, run_config):
        for chunk in cls.get_sql_chunks(run_config):
            yield from cls._yield_missing_in_es(chunk)

    @staticmethod
    def get_sql_chunks(run_config):
        domain = run_config.domain if run_config.domain is not ALL_DOMAINS else None

        accessor = CaseReindexAccessor(
            domain,
            start_date=run_config.start_date, end_date=run_config.end_date,
            case_type=run_config.case_type
        )
        iteration_key = f'sql_cases-{run_config.iteration_key}'
        for chunk in _get_resumable_chunked_iterator(accessor, iteration_key, '[SQL cases] '):
            matching_records = [
                (case.case_id, case.type, case.server_modified_on, case.domain)
                for case in chunk
            ]
            yield matching_records

    @staticmethod
    def _yield_missing_in_es(chunk):
        case_ids, case_search_ids = CaseHelper._get_ids_from_chunk(chunk)
        es_modified_on_by_ids = CaseHelper._get_es_modified_dates(case_ids)
        case_search_es_modified_on_by_ids = CaseHelper._get_case_search_es_modified_dates(case_search_ids)
        for case_id, case_type, modified_on, domain in chunk:
            stale, data_row = CaseHelper._check_stale(case_id, case_type, modified_on, domain,
                                                      es_modified_on_by_ids, case_search_es_modified_on_by_ids)
            if stale:
                yield data_row

    @staticmethod
    def _check_stale(case_id, case_type, modified_on, domain,
                     es_modified_on_by_ids, case_search_es_modified_on_by_ids):
        es_modified_on, es_domain = es_modified_on_by_ids.get(case_id, (None, None))
        if (es_modified_on, es_domain) != (modified_on, domain):
            # if the doc is newer in ES than sql, refetch from sql to get newest
            if es_modified_on is not None and es_modified_on > modified_on:
                refreshed = CommCareCase.objects.get_case(case_id, domain)
                if refreshed.server_modified_on != modified_on:
                    return CaseHelper._check_stale(case_id, case_type, refreshed.server_modified_on,
                                                   refreshed.domain, es_modified_on_by_ids,
                                                   case_search_es_modified_on_by_ids)
            return True, DataRow(doc_id=case_id, doc_type='CommCareCase', doc_subtype=case_type,
                                 domain=domain, es_date=es_modified_on, primary_date=modified_on)
        elif domain_needs_search_index(domain):
            es_modified_on, es_domain = case_search_es_modified_on_by_ids.get(case_id, (None, None))
            if (es_modified_on, es_domain) != (modified_on, domain):
                # if the doc is newer in ES than sql, refetch from sql to get newest
                if es_modified_on is not None and es_modified_on > modified_on:
                    refreshed = CommCareCase.objects.get_case(case_id, domain)
                    if refreshed.server_modified_on != modified_on:
                        return CaseHelper._check_stale(case_id, case_type, refreshed.server_modified_on,
                                                       refreshed.domain, es_modified_on_by_ids,
                                                       case_search_es_modified_on_by_ids)
                return True, DataRow(doc_id=case_id, doc_type='CommCareCase', doc_subtype=case_type,
                                     domain=domain, es_date=es_modified_on, primary_date=modified_on)
        return False, None

    @staticmethod
    @retry_on_es_timeout
    def _get_es_modified_dates(case_ids):
        results = (
            CaseES(for_export=True)
            .case_ids(case_ids)
            .values_list('_id', 'server_modified_on', 'domain')
        )
        return {_id: (iso_string_to_datetime(server_modified_on) if server_modified_on else None, domain)
                for _id, server_modified_on, domain in results}

    @staticmethod
    @retry_on_es_timeout
    def _get_case_search_es_modified_dates(case_ids):
        results = (
            CaseSearchES(for_export=True)
            .case_ids(case_ids)
            .values_list('_id', 'server_modified_on', 'domain')
        )
        return {_id: (iso_string_to_datetime(server_modified_on) if server_modified_on else None, domain)
                for _id, server_modified_on, domain in results}

    @staticmethod
    def _get_ids_from_chunk(chunk):
        case_ids = []
        case_search_ids = []
        for val in chunk:
            case_ids.append(val[0])
            if domain_needs_search_index(val[3]):
                case_search_ids.append(val[0])
        return case_ids, case_search_ids


class FormHelper:
    @classmethod
    def run(cls, run_config):
        for chunk in cls.get_sql_chunks(run_config):
            yield from cls._yield_missing_in_es(chunk)

    @staticmethod
    def get_sql_chunks(run_config):
        domain = run_config.domain if run_config.domain is not ALL_DOMAINS else None

        accessor = FormReindexAccessor(
            domain,
            start_date=run_config.start_date, end_date=run_config.end_date,
        )
        iteration_key = f'sql_forms-{run_config.iteration_key}'
        for chunk in _get_resumable_chunked_iterator(accessor, iteration_key, '[SQL forms] '):
            matching_records = [
                (form.form_id, form.doc_type, form.xmlns, form.received_on, form.domain)
                for form in chunk
                # Only check for "normal" and "archived" forms
                if form.is_normal or form.is_archived
            ]
            yield matching_records

    @staticmethod
    def _yield_missing_in_es(chunk):
        form_ids = [val[0] for val in chunk]
        es_modified_on_by_ids = FormHelper._get_es_modified_dates_for_forms(form_ids)
        for form_id, doc_type, xmlns, modified_on, domain in chunk:
            es_modified_on, es_doc_type, es_domain = es_modified_on_by_ids.get(form_id, (None, None, None))
            if (es_modified_on, es_doc_type, es_domain) != (modified_on, doc_type, domain):
                yield DataRow(doc_id=form_id, doc_type=doc_type, doc_subtype=xmlns, domain=domain,
                              es_date=es_modified_on, primary_date=modified_on)

    @staticmethod
    def _get_es_modified_dates_for_forms(form_ids):
        results = (
            FormES(for_export=True).remove_default_filters()
            .form_ids(form_ids)
            .values_list('_id', 'received_on', 'doc_type', 'domain')
        )
        return {_id: (iso_string_to_datetime(received_on), doc_type, domain)
                for _id, received_on, doc_type, domain in results}


def _get_resumable_chunked_iterator(dbaccessor, iteration_key, log_prefix):
    total_docs = 0
    for db in dbaccessor.sql_db_aliases:
        total_docs += dbaccessor.get_approximate_doc_count(db)

    iterable = resumable_sql_model_iterator(
        iteration_key,
        dbaccessor,
        chunk_size=CHUNK_SIZE,
        transform=lambda x: x
    )
    progress = ProgressManager(
        iterable,
        total=total_docs,
        reset=False,
        chunk_size=CHUNK_SIZE,
        logger=ProcessorProgressLogger(log_prefix, sys.stderr)
    )
    with progress:
        for chunk in chunked(iterable, CHUNK_SIZE):
            yield chunk
            progress.add(len(chunk))
