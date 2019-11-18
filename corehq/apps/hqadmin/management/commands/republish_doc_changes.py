from collections import namedtuple

from django.core.management import BaseCommand, CommandError

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.producer import producer
from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.utils import should_use_sql_backend
from dimagi.utils.chunked import chunked

from casexml.apps.case.models import CommCareCase
from corehq.doctypemigrations.continuous_migrate import bulk_get_revs
from corehq.apps.hqcase.management.commands.backfill_couch_forms_and_cases import (
    publish_change, create_case_change_meta
)
from pillowtop.feed.interface import ChangeMeta


DocumentRecord = namedtuple('DocumentRecord', ['doc_id', 'doc_type', 'doc_subtype'])


CASE_DOC_TYPE = "CommCareCase"
FORM_DOC_TYPE = "XFormInstance"


class Command(BaseCommand):
    """
    Republish doc changes. Meant to be used in conjunction with stale_data_in_es command

        $ ./manage.py republish_doc_changes <DOMAIN> <doc_ids.txt>
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('doc_ids_file')

    def handle(self, domain, doc_ids_file, *args, **options):
        document_records = _get_document_records(doc_ids_file)
        form_records = []
        case_records = []
        for record in document_records:
            if record.doc_type == CASE_DOC_TYPE:
                case_records.append(record)
            else:
                assert record.doc_type == FORM_DOC_TYPE
                form_records.append(record)

        _publish_cases(domain, case_records)
        _publish_forms(domain, form_records)


def _get_document_records(doc_ids_file):
    with open(doc_ids_file, 'r') as f:
        lines = f.readlines()
        for l in lines:
            doc_id, doc_type, doc_subtype = [val.strip() for val in l.split(',')[0:3]]
            if doc_type not in [CASE_DOC_TYPE, FORM_DOC_TYPE]:
                raise CommandError(f"Found bad doc type {doc_type}. "
                                   "Did you use the right command to create the data?")
            yield DocumentRecord(doc_id, doc_type, doc_subtype)


def _publish_cases(domain, case_records):
    if should_use_sql_backend(domain):
        _publish_cases_for_sql(domain, case_records)
    else:
        _publish_cases_for_couch(domain, [c.doc_id for c in case_records])


def _publish_forms(domain, form_records):
    if should_use_sql_backend(domain):
        _publish_forms_for_sql(domain, form_records)
    else:
        raise CommandError("Republishing forms for couch domains is not supported yet!")


def _publish_cases_for_couch(domain, case_ids):
    for ids in chunked(case_ids, 500):
        doc_id_rev_list = bulk_get_revs(CommCareCase.get_db(), ids)
        for doc_id, doc_rev in doc_id_rev_list:
            publish_change(
                create_case_change_meta(domain, doc_id, doc_rev)
            )


def _publish_cases_for_sql(domain, case_records):
    records_with_types = filter(lambda r: r.doc_subtype, case_records)
    records_with_no_types = filter(lambda r: not r.doc_subtype, case_records)
    # if we already had a type just publish as-is
    for record in records_with_types:
        producer.send_change(
            topics.CASE_SQL,
            _change_meta_for_sql_case(domain, record.doc_id, record.doc_subtype)
        )

    # else lookup the type from the database
    for record_chunk in chunked(records_with_no_types, 10000):
        # databases will contain a mapping of shard database ids to case_ids in that DB
        id_chunk = [r.doc_id for r in record_chunk]
        databases = ShardAccessor.get_docs_by_database(id_chunk)
        for db, doc_ids in databases.items():
            results = CommCareCaseSQL.objects.using(db).filter(
                case_id__in=doc_ids,
            ).values_list('case_id', 'type')
            # make sure we found the same number of IDs
            assert len(results) == len(doc_ids)
            for case_id, case_type in results:
                producer.send_change(
                    topics.CASE_SQL,
                    _change_meta_for_sql_case(domain, case_id, case_type)
                )


def _change_meta_for_sql_case(domain, case_id, case_type):
    return ChangeMeta(
        document_id=case_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.CASE_SQL,
        document_type=CASE_DOC_TYPE,
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


def _change_meta_for_sql_form_record(domain, form_record):
    return ChangeMeta(
        document_id=form_record.doc_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.FORM_SQL,
        document_type=FORM_DOC_TYPE,
        document_subtype=form_record.doc_subtype,
        domain=domain,
        is_deletion=False,
    )
