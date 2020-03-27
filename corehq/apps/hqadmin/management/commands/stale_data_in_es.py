import csv
import inspect
import sys
from collections import namedtuple
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

import dateutil
from django.db.models import F
from memoized import memoized

from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from couchforms.models import XFormInstance
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
from dimagi.utils.parsing import json_format_datetime

RunConfig = namedtuple('RunConfig', ['domain', 'start_date', 'end_date', 'case_type'])
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

        start = dateutil.parser.parse(options['start']) if options['start'] else datetime(2010, 1, 1)
        end = dateutil.parser.parse(options['end']) if options['end'] else datetime.utcnow()
        case_type = options['case_type']
        run_config = RunConfig(domain, start, end, case_type)

        if run_config.domain is ALL_DOMAINS:
            print('Running for all domains', file=self.stderr)

        csv_writer = csv.writer(self.stdout, **get_csv_args(delimiter))

        def print_data_row(data_row):
            # Casting as str print `None` as 'None'
            csv_writer.writerow(map(str, data_row))

        print_data_row(HEADER_ROW)

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
        for db in get_db_aliases_for_partitioned_query():
            matching_records_for_db = get_sql_case_data_for_db(db, run_config)

            yield from _chunked_with_progress_bar(matching_records_for_db, 1000,
                                                  prefix=f'Processing cases in DB {db}')

    @staticmethod
    def _get_couch_case_chunks(run_config):
        if run_config.case_type and run_config is not ALL_DOMAINS \
                and not _should_use_sql_backend(run_config.domain):
            raise CommandError('Case type argument is not supported for couch domains!')
        matching_records = CaseBackend._get_couch_case_data(run_config)
        print("Processing cases in Couch, which doesn't support nice progress bar", file=sys.stderr)
        yield from chunked(matching_records, 1000)

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
        for couch_domain in _get_matching_couch_domains(run_config):
            iterator = paginate_view(
                CommCareCase.get_db(),
                'cases_by_server_date/by_server_modified_on',
                chunk_size=1000,
                startkey=[couch_domain],
                endkey=[couch_domain, {}],
                include_docs=False,
                reduce=False,
            )
            for row in iterator:
                case_id, modified_on = row['id'], iso_string_to_datetime(row['value'])
                if run_config.start_date <= modified_on < run_config.end_date:
                    yield case_id, 'COUCH_TYPE_NOT_SUPPORTED', modified_on, couch_domain

    @staticmethod
    def _get_es_modified_dates(case_ids):
        results = (
            CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .case_ids(case_ids)
            .values_list('_id', 'server_modified_on', 'domain')
        )
        return {_id: (iso_string_to_datetime(server_modified_on), domain)
                for _id, server_modified_on, domain in results}


def get_sql_case_data_for_db(db, run_config):
    matching_cases = CommCareCaseSQL.objects.using(db).filter(
        server_modified_on__gte=run_config.start_date,
        server_modified_on__lte=run_config.end_date,
        deleted=False,
    )
    if run_config.domain is not ALL_DOMAINS:
        matching_cases = matching_cases.filter(
            domain=run_config.domain,
        )
    if run_config.case_type:
        matching_cases = matching_cases.filter(
            type=run_config.case_type
        )
    return [
        (*rest, domain)
        for *rest, domain in matching_cases.values_list('case_id', 'type', 'server_modified_on', 'domain')
        if _should_use_sql_backend(domain)
    ]


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
        for db in get_db_aliases_for_partitioned_query():
            matching_records_for_db = FormBackend._get_sql_form_data_for_db(db, run_config)
            yield from _chunked_with_progress_bar(matching_records_for_db, 1000,
                                                  prefix=f'Processing forms in DB {db}')

    @staticmethod
    def _get_couch_form_chunks(run_config):
        length, matching_records = FormBackend._get_couch_form_data(run_config)
        return _chunked_with_progress_bar(matching_records, 1000, length=length,
                                          prefix=f'Processing forms in Couch')

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
    def _get_sql_form_data_for_db(db, run_config):
        matching_forms = XFormInstanceSQL.objects.using(db).filter(
            received_on__gte=run_config.start_date,
            received_on__lte=run_config.end_date,
            # Only check for "normal" and "archived" forms
            state=F('state').bitand(XFormInstanceSQL.NORMAL) + F('state').bitand(XFormInstanceSQL.ARCHIVED)
        )
        if run_config.domain is not ALL_DOMAINS:
            matching_forms = matching_forms.filter(
                domain=run_config.domain
            )
        return [
            (form_id, state_to_doc_type.get(state, 'XFormInstance'), xmlns, received_on, domain)
            for form_id, state, xmlns, received_on, domain in matching_forms.values_list(
                'form_id', 'state', 'xmlns', 'received_on', 'domain')
            if _should_use_sql_backend(domain)
        ]

    @staticmethod
    def _get_couch_form_data(run_config):
        db = XFormInstance.get_db()
        view = 'by_domain_doc_type_date/view'

        def get_kwargs(couch_domain, doc_type):
            return dict(
                startkey=[couch_domain, doc_type, json_format_datetime(run_config.start_date)],
                endkey=[couch_domain, doc_type, json_format_datetime(run_config.end_date)],
            )

        def _get_length():
            length = 0
            for couch_domain in _get_matching_couch_domains(run_config):
                for doc_type in ['XFormArchived', 'XFormInstance']:
                    result = db.view(view, reduce=True, **get_kwargs(couch_domain, doc_type)).one()
                    if result:
                        length += result['value']
            return length

        def _yield_records():
            for couch_domain in _get_matching_couch_domains(run_config):
                for doc_type in ['XFormArchived', 'XFormInstance']:
                    iterator = paginate_view(
                        db,
                        view,
                        reduce=False,
                        include_docs=False,
                        chunk_size=1000,
                        **get_kwargs(couch_domain, doc_type)
                    )
                    for row in iterator:
                        form_id = row['id']
                        domain, doc_type, received_on = row['key']
                        received_on = iso_string_to_datetime(received_on)
                        assert run_config.domain in (domain, ALL_DOMAINS)
                        yield (form_id, doc_type, 'COUCH_XMLNS_NOT_SUPPORTED',
                               received_on, domain)
        return _get_length(), _yield_records()

    @staticmethod
    def _get_es_modified_dates_for_forms(form_ids):
        results = (
            FormES(es_instance_alias=ES_EXPORT_INSTANCE).remove_default_filters()
            .form_ids(form_ids)
            .values_list('_id', 'received_on', 'doc_type', 'domain')
        )
        return {_id: (iso_string_to_datetime(received_on), doc_type, domain)
                for _id, received_on, doc_type, domain in results}


def _chunked_with_progress_bar(collection, n, prefix, **kwargs):
    return chunked(with_progress_bar(collection, prefix=prefix, stream=sys.stderr, **kwargs), n)


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
