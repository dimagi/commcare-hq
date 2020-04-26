import csv
import inspect
import sys
from collections import namedtuple
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

import dateutil

from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from dimagi.utils.chunked import chunked
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.domain.models import Domain
from corehq.apps.es import CaseES, FormES
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseReindexAccessor,
    FormReindexAccessor,
)
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.dates import iso_string_to_datetime
from corehq.util.doc_processor.couch import resumable_view_iterator
from corehq.util.doc_processor.progress import (
    ProcessorProgressLogger,
    ProgressManager,
)
from corehq.util.doc_processor.sql import resumable_sql_model_iterator
from corehq.util.pagination import PaginationEventHandler
from memoized import memoized

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
                    process_data_model_fn = DATA_MODEL_BACKENDS[data_model.lower()]()
                except KeyError:
                    raise CommandError('Only valid options for data model are "{}"'.format(
                        '", "'.join(DATA_MODEL_BACKENDS.keys())
                    ))
                data_rows = process_data_model_fn(run_config)

                for data_row in data_rows:
                    print_data_row(data_row)
        except:
            print(f'\nERROR: To resume the previous run add the "iteration_key" parameter to the command:\n'
                  f"\t--iteration_key '{iteration_key}'\n", file=self.stderr)
            raise


DATA_MODEL_BACKENDS = {
    'case': lambda: CaseBackend.run,
    'form': lambda: FormBackend.run,
}


class CaseBackend:
    @staticmethod
    def run(run_config):
        for chunk in CaseBackend._get_case_chunks(run_config):
            yield from CaseBackend._yield_missing_in_es(chunk)

    @staticmethod
    def _get_case_chunks(run_config):
        yield from CaseBackend._get_sql_case_chunks(run_config)
        yield from CaseBackend._get_couch_case_chunks(run_config)

    @staticmethod
    def _get_sql_case_chunks(run_config):
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
                if _should_use_sql_backend(case.domain)
            ]
            yield matching_records

    @staticmethod
    def _get_couch_case_chunks(run_config):
        if run_config.case_type and run_config is not ALL_DOMAINS \
                and not _should_use_sql_backend(run_config.domain):
            raise CommandError('Case type argument is not supported for couch domains!')
        matching_records = CaseBackend._get_couch_case_data(run_config)
        print("Processing cases in Couch, which doesn't support nice progress bar", file=sys.stderr)
        yield from chunked(matching_records, CHUNK_SIZE)

    @staticmethod
    def _yield_missing_in_es(chunk):
        case_ids = [val[0] for val in chunk]
        es_modified_on_by_ids = CaseBackend._get_es_modified_dates(case_ids)
        for case_id, case_type, modified_on, domain in chunk:
            es_modified_on, es_domain = es_modified_on_by_ids.get(case_id, (None, None))
            if (es_modified_on, es_domain) != (modified_on, domain):
                yield DataRow(doc_id=case_id, doc_type='CommCareCase', doc_subtype=case_type, domain=domain,
                              es_date=es_modified_on, primary_date=modified_on)

    @staticmethod
    def _get_couch_case_data(run_config):
        view_name = 'cases_by_server_date/by_server_modified_on'

        keys = [[couch_domain] for couch_domain in _get_matching_couch_domains(run_config)]
        if not keys:
            return

        iteration_key = f'couch_cases-{run_config.iteration_key}'
        event_handler = ProgressEventHandler(iteration_key, 'unknown', sys.stderr)
        iterable = resumable_view_iterator(
            CommCareCase.get_db(), iteration_key, view_name, keys,
            chunk_size=CHUNK_SIZE, view_event_handler=event_handler, full_row=True
        )
        for row in iterable:
            case_id, domain, modified_on = row['id'], row['key'][0], iso_string_to_datetime(row['value'])
            if run_config.start_date <= modified_on < run_config.end_date:
                yield case_id, 'COUCH_TYPE_NOT_SUPPORTED', modified_on, domain

    @staticmethod
    def _get_es_modified_dates(case_ids):
        results = (
            CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .case_ids(case_ids)
            .values_list('_id', 'server_modified_on', 'domain')
        )
        return {_id: (iso_string_to_datetime(server_modified_on), domain)
                for _id, server_modified_on, domain in results}


class FormBackend:
    @staticmethod
    def run(run_config):
        for chunk in FormBackend._get_form_chunks(run_config):
            yield from FormBackend._yield_missing_in_es(chunk)

    @staticmethod
    def _get_form_chunks(run_config):
        yield from FormBackend._get_sql_form_chunks(run_config)
        yield from FormBackend._get_couch_form_chunks(run_config)

    @staticmethod
    def _get_sql_form_chunks(run_config):
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
                if (
                    _should_use_sql_backend(form.domain) and
                    # Only check for "normal" and "archived" forms
                    (form.is_normal or form.is_archived)
                )
            ]
            yield matching_records

    @staticmethod
    def _get_couch_form_chunks(run_config):
        db = XFormInstance.get_db()
        view_name = 'by_domain_doc_type_date/view'

        keys = [
            {
                'startkey': [couch_domain, doc_type, json_format_datetime(run_config.start_date)],
                'endkey': [couch_domain, doc_type, json_format_datetime(run_config.end_date)],
            }
            for couch_domain in _get_matching_couch_domains(run_config)
            for doc_type in ['XFormArchived', 'XFormInstance']
        ]
        if not keys:
            return

        def _get_length():
            length = 0
            for key in keys:
                result = db.view(view_name, reduce=True, **key).one()
                if result:
                    length += result['value']
            return length

        iteration_key = f'couch_forms-{run_config.iteration_key}'
        iterable = resumable_view_iterator(
            XFormInstance.get_db(), iteration_key, view_name, keys,
            chunk_size=CHUNK_SIZE, full_row=True
        )
        progress = ProgressManager(
            iterable,
            total=_get_length(),
            reset=False,
            chunk_size=CHUNK_SIZE,
            logger=ProcessorProgressLogger('[Couch Forms] ', sys.stderr)
        )
        with progress:
            for chunk in chunked(iterable, CHUNK_SIZE):
                records = []
                for row in chunk:
                    form_id = row['id']
                    domain, doc_type, received_on = row['key']
                    received_on = iso_string_to_datetime(received_on)
                    assert run_config.domain in (domain, ALL_DOMAINS)
                    records.append((form_id, doc_type, 'COUCH_XMLNS_NOT_SUPPORTED', received_on, domain))
                yield records
                progress.add(len(chunk))

    @staticmethod
    def _yield_missing_in_es(chunk):
        form_ids = [val[0] for val in chunk]
        es_modified_on_by_ids = FormBackend._get_es_modified_dates_for_forms(form_ids)
        for form_id, doc_type, xmlns, modified_on, domain in chunk:
            es_modified_on, es_doc_type, es_domain = es_modified_on_by_ids.get(form_id, (None, None, None))
            if (es_modified_on, es_doc_type, es_domain) != (modified_on, doc_type, domain):
                yield DataRow(doc_id=form_id, doc_type=doc_type, doc_subtype=xmlns, domain=domain,
                              es_date=es_modified_on, primary_date=modified_on)

    @staticmethod
    def _get_es_modified_dates_for_forms(form_ids):
        results = (
            FormES(es_instance_alias=ES_EXPORT_INSTANCE).remove_default_filters()
            .form_ids(form_ids)
            .values_list('_id', 'received_on', 'doc_type', 'domain')
        )
        return {_id: (iso_string_to_datetime(received_on), doc_type, domain)
                for _id, received_on, doc_type, domain in results}


@memoized
def _should_use_sql_backend(domain):
    return should_use_sql_backend(domain)


@memoized
def _get_matching_couch_domains(run_config):
    if run_config.domain is ALL_DOMAINS:
        return [domain.name for domain in Domain.get_all() if not _should_use_sql_backend(domain)]
    elif _should_use_sql_backend(run_config.domain):
        return []
    else:
        return [run_config.domain]


class ProgressEventHandler(PaginationEventHandler):

    def __init__(self, log_prefix, total, stream=None):
        self.log_prefix = log_prefix
        self.stream = stream
        self.total = total

    def page_end(self, total_emitted, duration, *args, **kwargs):
        print(f'{self.log_prefix} Processed {total_emitted} of {self.total} in {duration}', file=self.stream)


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
