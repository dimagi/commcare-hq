import csv
import io
import time

from django.core.management.base import BaseCommand, CommandError

import sqlalchemy

from corehq.apps.hqadmin.utils import get_download_url
from corehq.apps.project_db.schema import (
    get_project_db_engine,
    get_schema_name,
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
        engine = get_project_db_engine()
        schema_name = get_schema_name(domain)

        inspector = sqlalchemy.inspect(engine)
        if schema_name not in inspector.get_schema_names():
            raise CommandError(
                f"No project DB schema found for domain '{domain}'."
            )

        with engine.begin() as conn:
            # Use execution_options postgresql_readonly in sqlalchemy 1.4+
            conn.execute(sqlalchemy.text('SET TRANSACTION READ ONLY'))
            conn.execute(sqlalchemy.text(f'SET LOCAL search_path TO "{schema_name}"'))
            start = time.monotonic()
            result = conn.execute(sqlalchemy.text(sql))
            rows = result.fetchall()
            elapsed = time.monotonic() - start
            columns = list(result.keys())

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
