from __future__ import absolute_import, print_function

from __future__ import unicode_literals
from collections import defaultdict
from collections import namedtuple

import sys
from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor, CaseReindexAccessor
from corehq.util.markup import SimpleTableWriter, TableRowFormatter, CSVRowFormatter


class DocCountInfo(namedtuple('DocCountInfo', 'total by_db by_host')):
    @property
    def by_db_table(self):
        return [
            (db, self.by_db[db], 100 * self.by_db[db] // self.total)
            for db in sorted(self.by_db)
        ]

    @property
    def by_host_table(self):
        return [
            (host, self.by_host[host], 100 * self.by_host[host] // self.total)
            for host in sorted(self.by_host)
        ]


class Command(BaseCommand):
    help = (
        "Print approximate form and case counts per database and per host. "
        "This command is quick to run and useful for doing basic checks or"
        "getting rough distributions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            action='store_true',
            dest='csv',
            default=False,
        )

    def handle(self, **options):
        csv_mode = options['csv']

        form_info = _get_counts(FormReindexAccessor())
        case_info = _get_counts(CaseReindexAccessor())

        if csv_mode:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter([20, 20, 10])

        _write_info('FORMS', form_info, row_formatter, self.stdout)
        _write_info('CASES', case_info, row_formatter, self.stdout)


def _write_info(title, info, row_formatter, out=None):
    out = out or sys.stdout
    writer = SimpleTableWriter(out, row_formatter)

    out.write('\n{}\n'.format(title))
    out.write('{}\n'.format(row_formatter.format_row(['Total', info.total, ''])))

    out.write('\nBy DB\n'.format(info.total))
    writer.write_table(['DB', '# Docs', '%'], info.by_db_table)

    out.write('\nBy Host\n'.format(info.total))
    writer.write_table(['Host', '# Docs', '%'], info.by_host_table)


def _get_counts(accessor):
    total = 0
    by_host = defaultdict(int)
    by_db = {}
    for db in accessor.sql_db_aliases:
        count = accessor.get_approximate_doc_count(db)
        total += count
        by_db[db] = count
        by_host[settings.DATABASES[db]['HOST']] += count
    return DocCountInfo(total, by_db, by_host)
