from django.core.management.base import BaseCommand, CommandError

import dateutil.parser

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.project_db.populate import case_to_row_dict, upsert_case
from corehq.apps.project_db.schema import (
    get_project_db_engine,
    sync_domain_tables,
)
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseReindexAccessor,
    iter_all_rows,
)
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = (
        "Populate project DB tables for a domain from its data dictionary "
        "and case data."
    )

    def add_arguments(self, parser):
        parser.add_argument('domain', help="The project domain to populate.")
        parser.add_argument(
            '--since',
            help=(
                "Only process cases modified on or after this date "
                "(ISO 8601, e.g. 2026-01-15 or 2026-01-15T08:00:00)."
            ),
        )

    def handle(self, domain, since, **options):
        case_types = list(
            CaseType.objects.filter(domain=domain, is_deprecated=False)
            .values_list('name', flat=True)
            .order_by('name')
        )

        if not case_types:
            raise CommandError(
                f"No active case types found for domain '{domain}'. "
                "Check that the data dictionary is populated."
            )

        start_date = None
        if since:
            try:
                start_date = dateutil.parser.parse(since)
            except (ValueError, OverflowError):
                raise CommandError(f"Invalid --since date: {since!r}")

        engine = get_project_db_engine()
        tables = sync_domain_tables(engine, domain)

        for case_type in case_types:
            table = tables[case_type]
            self._populate_case_type(
                engine, domain, case_type, table, start_date,
            )

    def _populate_case_type(self, engine, domain, case_type, table, start_date):
        accessor = CaseReindexAccessor(
            domain=domain,
            case_type=case_type,
            start_date=start_date,
        )
        cases = iter_all_rows(accessor)
        total = sum(accessor.get_approximate_doc_count(db)
                    for db in accessor.sql_db_aliases)

        self.stdout.write(f"\n{case_type}")
        with engine.begin() as conn:
            for case in with_progress_bar(cases, length=total, oneline='concise'):
                row_dict = case_to_row_dict(case)
                upsert_case(conn, table, row_dict)
