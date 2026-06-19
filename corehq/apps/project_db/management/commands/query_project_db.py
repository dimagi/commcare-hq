import csv
import io
import time

from django.core.management.base import BaseCommand

import sqlalchemy

from corehq.apps.hqadmin.utils import get_download_url
from corehq.apps.project_db.table_ddl import (
    DomainSchema,
    get_project_db_engine,
)
from corehq.util.markup import SimpleTableWriter, TableRowFormatter

DEFAULT_ROW_LIMIT = 30

_HELP = """Execute a read-only SQL query against a domain's project DB tables.

Tables are accessible by case type name (e.g. 'patient', 'household').
By default the first {limit} rows are printed to the terminal. Pass --full to
fetch every row instead, upload them as a CSV, and print a download URL.

Example:

    ./manage.py query_project_db my-domain \\
        "SELECT p.case_name, h.prop__district
         FROM patient p
         JOIN household h ON p.parent_id = h.case_id
         WHERE p.prop__dob__date > '2000-01-01'"
""".format(limit=DEFAULT_ROW_LIMIT)


class Command(BaseCommand):
    help = _HELP

    def add_arguments(self, parser):
        parser.add_argument('domain', help="The project domain to query.")
        parser.add_argument('sql', help="SQL query to execute.")
        parser.add_argument(
            '--full',
            action='store_true',
            help="Fetch all rows and upload them as a CSV instead of printing "
                 f"the first {DEFAULT_ROW_LIMIT} to the terminal.",
        )

    def handle(self, domain, sql, full, **options):
        start = time.monotonic()
        engine = get_project_db_engine()

        with engine.begin() as conn:
            # In sqlalchemy 1.4+, use execution_options postgresql_readonly
            conn.execute(sqlalchemy.text('SET TRANSACTION READ ONLY'))
            DomainSchema(domain).set_local_search_path(conn)
            result = conn.execute(sqlalchemy.text(sql))
            columns = list(result.keys())
            if full:
                rows = result.fetchall()
            else:
                # Fetch one extra row to detect whether results were truncated
                rows = result.fetchmany(DEFAULT_ROW_LIMIT + 1)

        elapsed = time.monotonic() - start
        if full:
            self._report_full(domain, columns, rows, elapsed)
        else:
            self._report_preview(columns, rows, elapsed)

    def _report_preview(self, columns, rows, elapsed):
        rows = rows[:DEFAULT_ROW_LIMIT]
        self.stdout.write(f"{len(rows)} rows returned in {elapsed:.3f}s.")
        writer = SimpleTableWriter(self.stdout, TableRowFormatter())
        writer.write_table(columns, rows)
        if len(rows) > DEFAULT_ROW_LIMIT:
            self.stdout.write(f"\nShowing the first {DEFAULT_ROW_LIMIT} rows. "
                              "Pass --full to fetch all rows as a CSV.")

    def _report_full(self, domain, columns, rows, elapsed):
        self.stdout.write(f"{len(rows)} rows returned in {elapsed:.3f}s.")
        if not rows:
            return
        csv_content = self._write_csv(columns, rows)
        url = get_download_url(csv_content, f'{domain}_query_results.csv', 'text/csv')
        self.stdout.write(f"Download: {url}")

    def _write_csv(self, columns, rows):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        writer.writerows(rows)
        return io.BytesIO(buf.getvalue().encode('utf-8'))
