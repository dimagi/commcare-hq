from django.core.management.base import BaseCommand

from corehq.apps.data_pipeline_audit.tools import get_doc_counts_for_domain
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.util.markup import (
    CSVRowFormatter,
    SimpleTableWriter,
    TableRowFormatter,
)


class Command(BaseCommand):
    help = "Print doc counts in ES & Primary database split by Doc Type."

    def add_arguments(self, parser):
        parser.add_argument('domains', nargs='*')
        parser.add_argument('--csv', action='store_true', default=False, dest='csv',
                            help='Write output in CSV format.')

    def handle(self, domains, **options):
        csv = options.get('csv')

        if csv:
            row_formatter = CSVRowFormatter()
        else:
            dom_len = max(len(domain) for domain in domains) + 2
            row_formatter = TableRowFormatter(
                [dom_len, 7, 50, 15, 15],
                _get_row_color
            )

        writer = SimpleTableWriter(self.stdout, row_formatter)
        writer.write_headers(['Domain', 'Backend', 'Doc Type', 'Primary', 'ES'])
        for domain in domains:
            backend = 'sql' if should_use_sql_backend(domain) else 'couch'
            rows = get_doc_counts_for_domain(domain)
            writer.write_rows(((domain, backend) + row for row in rows))


def _get_row_color(row):
    domain, backend, doc_type, primary_count, es_count = row
    if primary_count != es_count:
        return 'red'
