import csv

from django.core.management import BaseCommand, CommandError
from memoized import memoized

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.hqadmin.management.commands.stale_data_in_es import DataRow, HEADER_ROW, get_csv_args
from corehq.toggles import DO_NOT_REPUBLISH_DOCS

from pillowtop.feed.interface import ChangeMeta


DOC_TYPE_MAP = {
    'CommCareCase': (topics.CASE_SQL, data_sources.CASE_SQL),
    'XFormInstance': (topics.FORM_SQL, data_sources.FORM_SQL),
    'XFormArchived': (topics.FORM_SQL, data_sources.FORM_SQL),
}


class Command(BaseCommand):
    """
    Republish doc changes. Meant to be used in conjunction with stale_data_in_es command

        $ ./manage.py republish_doc_changes changes.tsv
    """

    def add_arguments(self, parser):
        parser.add_argument('stale_data_in_es_file')
        parser.add_argument('--delimiter', default='\t', choices=('\t', ','))
        parser.add_argument('--skip_domains', action='store_true')

    def handle(self, stale_data_in_es_file, delimiter, skip_domains, *args, **options):
        changes = _iter_changes(stale_data_in_es_file, skip_domains, delimiter=delimiter)
        for topic, meta in changes:
            producer.send_change(topic, meta)


def _iter_changes(stale_data_in_es_file, skip_domains, delimiter):
    with open(stale_data_in_es_file, 'r') as f:
        csv_reader = csv.reader(f, **get_csv_args(delimiter))
        for csv_row in csv_reader:
            data_row = DataRow(*csv_row)
            if skip_domains and should_not_republish_docs(data_row.domain):
                continue
            # Skip the header row anywhere in the file.
            # The "anywhere in the file" part is useful
            # if you cat multiple stale_data_in_es_file files together.
            if data_row != HEADER_ROW:
                try:
                    topic, source = DOC_TYPE_MAP[data_row.doc_type]
                except KeyError:
                    raise CommandError(f"Found bad doc type {data_row.doc_type}. "
                        "Did you use the right command to create the data?")
                yield topic, _change_meta(data_row, source)


@memoized
def should_not_republish_docs(domain):
    return DO_NOT_REPUBLISH_DOCS.enabled(domain)


def _change_meta(data_row, source):
    return ChangeMeta(
        document_id=data_row.doc_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=source,
        document_type=data_row.doc_type,
        document_subtype=data_row.doc_subtype,
        domain=data_row.domain,
        is_deletion=False,
    )
