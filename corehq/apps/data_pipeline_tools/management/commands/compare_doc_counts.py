from collections import Counter

from django.core.management.base import BaseCommand

from corehq.apps import es
from corehq.apps.data_pipeline_tools.dbacessors import (
    get_primary_db_form_counts,
    get_primary_db_case_counts,
    get_es_counts_by_doc_type)
from corehq.apps.data_pipeline_tools.utils import map_counter_doc_types
from corehq.util.markup import ConsoleTableWriter, CSVRowFormatter, \
    TableRowFormatter


class Command(BaseCommand):
    help = "Print doc counts in ES & Primary database split by Doc Type."
    args = '<domain>'

    def add_arguments(self, parser):
        parser.add_argument('--csv', action='store_true', default=False, dest='csv',
                            help='Write output in CSV format.')

    def handle(self, domain, **options):
        csv = options.get('csv')

        primary_db_counts = map_counter_doc_types(_get_primary_db_counts(domain))
        es_counts = map_counter_doc_types(get_es_counts_by_doc_type(domain, _es_indices()))
        all_doc_types = set(primary_db_counts) | set(es_counts)

        output_rows = []
        for doc_type in sorted(all_doc_types, key=lambda d: d.lower()):
            output_rows.append((
                doc_type,
                primary_db_counts.get(doc_type, 0),
                es_counts.get(doc_type, 0)
            ))

        if csv:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter(
                [50, 20, 20],
                _get_row_color
            )

        ConsoleTableWriter(['Doc Type', 'Primary', 'ES'], row_formatter).write(output_rows, self.stdout)


def _get_row_color(row):
    doc_type, primary_count, es_count = row
    if primary_count != es_count:
        return 'red'


def _get_primary_db_counts(domain):
    db_counts = Counter()
    db_counts.update(get_primary_db_form_counts(domain))
    db_counts.update(get_primary_db_case_counts(domain))
    return db_counts


def _es_indices():
    return es.CaseES, es.FormES
