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

_HELP = """Execute a read-only SQL query against a domain's project DB tables.

Tables are accessible by case type name (e.g. 'patient', 'household').
Results are uploaded as a CSV and a download URL is printed.

Example:

    ./manage.py query_project_db my-domain \\
        "SELECT p.case_name, h.prop__district
         FROM patient p
         JOIN household h ON p.parent_id = h.case_id
         WHERE p.prop__dob__date > '2000-01-01'"
"""


class Command(BaseCommand):
    help = _HELP

    def add_arguments(self, parser):
        parser.add_argument('domain', help="The project domain to query.")
        parser.add_argument('sql', help="SQL query to execute.")

    def handle(self, domain, sql, **options):
        start = time.monotonic()
        engine = get_project_db_engine()

        with engine.begin() as conn:
            # In sqlalchemy 1.4+, use execution_options postgresql_readonly
            conn.execute(sqlalchemy.text('SET TRANSACTION READ ONLY'))
            DomainSchema(domain).set_local_search_path(conn)
            result = conn.execute(sqlalchemy.text(sql))
            rows = result.fetchall()
            columns = list(result.keys())

        elapsed = time.monotonic() - start
        self.stdout.write(f"{len(rows)} rows returned in {elapsed:.3f}s.")
        if not rows:
            return

        csv_content = self._write_csv(columns, rows)
        url = get_download_url(
            csv_content, f'{domain}_query_results.csv', 'text/csv',
        )
        self.stdout.write(f"Download: {url}")

    def _write_csv(self, columns, rows):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        writer.writerows(rows)
        return io.BytesIO(buf.getvalue().encode('utf-8'))
