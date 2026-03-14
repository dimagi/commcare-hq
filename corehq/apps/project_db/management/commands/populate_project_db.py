from django.core.management.base import BaseCommand, CommandError

import dateutil.parser

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.project_db.populate import case_to_row_dict, upsert_case
from corehq.apps.project_db.schema import (
    build_tables_for_domain,
    create_tables,
    evolve_table,
    get_project_db_engine,
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
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--all',
            action='store_true',
            dest='all_case_types',
            help="Populate tables for all active case types on the domain.",
        )
        group.add_argument(
            '--case-types',
            help="Comma-separated list of case types to populate.",
        )
        parser.add_argument(
            '--since',
            help=(
                "Only process cases modified on or after this date "
                "(ISO 8601, e.g. 2026-01-15 or 2026-01-15T08:00:00)."
            ),
        )

    def handle(self, domain, all_case_types, case_types, since, **options):
        available_types = list(
            CaseType.objects.filter(domain=domain, is_deprecated=False)
            .values_list('name', flat=True)
            .order_by('name')
        )

        if not available_types:
            raise CommandError(
                f"No active case types found for domain '{domain}'. "
                "Check that the data dictionary is populated."
            )

        if not all_case_types and not case_types:
            self.stderr.write(
                f"Please specify --all or --case-types. "
                f"Active case types for '{domain}':\n"
            )
            for name in available_types:
                self.stderr.write(f"  - {name}\n")
            return

        if case_types:
            requested = [t.strip() for t in case_types.split(',')]
            unknown = set(requested) - set(available_types)
            if unknown:
                raise CommandError(
                    f"Unknown case types: {', '.join(sorted(unknown))}. "
                    f"Available: {', '.join(available_types)}"
                )
            selected_types = requested
        else:
            selected_types = available_types

        start_date = None
        if since:
            try:
                start_date = dateutil.parser.parse(since)
            except (ValueError, OverflowError):
                raise CommandError(f"Invalid --since date: {since!r}")

        engine = get_project_db_engine()
        tables = self._build_and_sync_tables(engine, domain, selected_types)

        for case_type in selected_types:
            table = tables[case_type]
            self._populate_case_type(
                engine, domain, case_type, table, start_date,
            )

    def _build_and_sync_tables(self, engine, domain, selected_types):
        """Build table schemas from the data dictionary and sync DDL."""
        import sqlalchemy
        metadata = sqlalchemy.MetaData()
        all_tables = build_tables_for_domain(metadata, domain)
        tables = {name: all_tables[name] for name in selected_types}

        create_tables(engine, metadata)
        for table in tables.values():
            evolve_table(engine, table)

        return tables

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
