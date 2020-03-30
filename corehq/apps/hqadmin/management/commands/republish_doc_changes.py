import csv
import itertools
from collections import namedtuple

from django.core.management import BaseCommand, CommandError

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.hqadmin.management.commands.stale_data_in_es import DataRow, HEADER_ROW, get_csv_args
from corehq.form_processor.utils import should_use_sql_backend
from couchforms.models import XFormInstance
from dimagi.utils.chunked import chunked

from casexml.apps.case.models import CommCareCase
from corehq.util.couch import bulk_get_revs
from corehq.apps.hqcase.management.commands.backfill_couch_forms_and_cases import (
    create_case_change_meta,
    create_form_change_meta,
    publish_change,
)
from pillowtop.feed.interface import ChangeMeta


DocumentRecord = namedtuple('DocumentRecord', ['doc_id', 'doc_type', 'doc_subtype', 'domain'])


CASE_DOC_TYPES = {'CommCareCase'}
FORM_DOC_TYPES = {'XFormInstance', 'XFormArchived'}

ALL_DOC_TYPES = set.union(CASE_DOC_TYPES, FORM_DOC_TYPES)


class Command(BaseCommand):
    """
    Republish doc changes. Meant to be used in conjunction with stale_data_in_es command

        $ ./manage.py republish_doc_changes changes.tsv
    """

    def add_arguments(self, parser):
        parser.add_argument('stale_data_in_es_file')
        parser.add_argument('--delimiter', default='\t', choices=('\t', ','))

    def handle(self, stale_data_in_es_file, delimiter, *args, **options):
        data_rows = _get_data_rows(stale_data_in_es_file, delimiter=delimiter)
        document_records = _get_document_records(data_rows)
        form_records = []
        case_records = []
        for record in document_records:
            if record.doc_type in CASE_DOC_TYPES:
                case_records.append(record)
            elif record.doc_type in FORM_DOC_TYPES:
                form_records.append(record)
            else:
                assert False, f'Bad doc type {record.doc_type} should have been caught already below.'
        _publish_cases(case_records)
        _publish_forms(form_records)


def _get_data_rows(stale_data_in_es_file, delimiter):
    with open(stale_data_in_es_file, 'r') as f:
        csv_reader = csv.reader(f, **get_csv_args(delimiter))
        for csv_row in csv_reader:
            data_row = DataRow(*csv_row)
            # Skip the header row anywhere in the file.
            # The "anywhere in the file" part is useful
            # if you cat multiple stale_data_in_es_file files together.
            if data_row != HEADER_ROW:
                yield data_row


def _get_document_records(data_rows):
    for data_row in data_rows:
        doc_id, doc_type, doc_subtype, domain = \
            data_row.doc_id, data_row.doc_type, data_row.doc_subtype, data_row.domain
        if doc_type not in ALL_DOC_TYPES:
            raise CommandError(f"Found bad doc type {doc_type}. "
                               "Did you use the right command to create the data?")
        yield DocumentRecord(doc_id, doc_type, doc_subtype, domain)


def _publish_cases(case_records):
    for domain, records in itertools.groupby(case_records, lambda r: r.domain):
        if should_use_sql_backend(domain):
            _publish_cases_for_sql(domain, list(records))
        else:
            _publish_cases_for_couch(domain, list(records))


def _publish_forms(form_records):
    for domain, records in itertools.groupby(form_records, lambda r: r.domain):
        if should_use_sql_backend(domain):
            _publish_forms_for_sql(domain, records)
        else:
            _publish_forms_for_couch(domain, records)


def _publish_cases_for_couch(domain, case_records):
    _publish_docs_for_couch(CommCareCase, create_case_change_meta, domain, case_records)


def _publish_cases_for_sql(domain, case_records):
    for record in case_records:
        producer.send_change(
            topics.CASE_SQL,
            _change_meta_for_sql_case(domain, record.doc_id, record.doc_subtype)
        )


def _change_meta_for_sql_case(domain, case_id, case_type):
    doc_type, = CASE_DOC_TYPES
    return ChangeMeta(
        document_id=case_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.CASE_SQL,
        document_type=doc_type,
        document_subtype=case_type,
        domain=domain,
        is_deletion=False,
    )


def _publish_forms_for_sql(domain, form_records):
    for record in form_records:
        producer.send_change(
            topics.FORM_SQL,
            _change_meta_for_sql_form_record(domain, record)
        )


def _publish_forms_for_couch(domain, form_records):
    _publish_docs_for_couch(XFormInstance, create_form_change_meta, domain, form_records)


def _change_meta_for_sql_form_record(domain, form_record):
    return ChangeMeta(
        document_id=form_record.doc_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.FORM_SQL,
        document_type=form_record.doc_type,
        document_subtype=form_record.doc_subtype,
        domain=domain,
        is_deletion=False,
    )


def _publish_docs_for_couch(doc_cls, get_meta, domain, records):
    doc_ids = [r.doc_id for r in records]
    for ids in chunked(doc_ids, 500):
        doc_id_rev_list = bulk_get_revs(doc_cls.get_db(), ids)
        for doc_id, doc_rev in doc_id_rev_list:
            publish_change(
                get_meta(domain, doc_id, doc_rev)
            )
