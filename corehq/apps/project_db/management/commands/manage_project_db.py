from textwrap import dedent

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import dateutil.parser
import sqlalchemy
from sqlalchemy.schema import CreateIndex, CreateTable

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.project_db.populate import send_to_project_db
from corehq.apps.project_db.table_ddl import (
    DomainSchema,
    create_or_update_project_db,
    create_project_db_extensions,
    get_project_db_engine,
    preview_drop,
)
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseReindexAccessor,
    iter_all_rows,
)
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Manage a domain's ProjectDB"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--sync',
            action='store_true',
            help="Create or update the domain's ProjectDB table schemas.",
        )
        parser.add_argument(
            '--drop',
            action='store_true',
            help="Drop the domain's ProjectDB schema, including all tables and data",
        )
        parser.add_argument(
            '--populate',
            action='store_true',
            help="Populate the domain's ProjectDB tables from case data.",
        )
        parser.add_argument(
            '--since',
            type=dateutil.parser.parse,
            help=(
                "Only process cases modified on or after this date "
                "(ISO 8601, e.g. 2026-01-15 or 2026-01-15T08:00:00)."
            ),
        )
        parser.add_argument(
            '--describe',
            action='store_true',
            help="Describe the tables in the domain's ProjectDB",
        )

    def handle(self, domain, sync, drop, populate, since, describe, **options):
        if drop and (sync or populate):
            raise CommandError("--drop cannot be combined with --sync or --populate.")
        if since and not populate:
            raise CommandError("--since is only used in conjunction with --populate.")

        if sync:
            if settings.DEBUG:
                create_project_db_extensions()
            create_or_update_project_db(domain)
            self.stdout.write("Synced ProjectDB table definition")
        if populate:
            _populate(domain, since)
            self.stdout.write("Populated ProjectDB")
        if drop:
            _drop(domain, self.stdout)
        if describe:
            _describe(domain)


def _drop(domain, stdout):
    schema = DomainSchema(domain)
    engine = get_project_db_engine()
    if schema.name not in sqlalchemy.inspect(engine).get_schema_names():
        stdout.write(f"No ProjectDB schema found for domain '{domain}'")
        return

    stdout.write("The following objects will be dropped:")
    for notice in preview_drop(domain):
        stdout.write(notice.rstrip())

    if input("confirm (y/N): ").strip().lower() in ('y', 'yes'):
        with engine.begin() as conn:
            schema.drop(conn)
        stdout.write("Dropped ProjectDB schema")
    else:
        stdout.write("Aborted; nothing was dropped")


def _populate(domain, start_date):
    case_types = CaseType.objects.filter(
        domain=domain,
        is_deprecated=False
    ).values_list('name', flat=True)

    for i, case_type in enumerate(case_types, 1):
        _populate_case_type(domain, case_type, start_date, f"{i}/{len(case_types)}")


def _populate_case_type(domain, case_type, start_date, prefix):
    accessor = CaseReindexAccessor(domain=domain, case_type=case_type, start_date=start_date)
    total = sum(accessor.query(db).count() for db in accessor.sql_db_aliases)
    cases = with_progress_bar(iter_all_rows(accessor), length=total,
                              oneline='concise', prefix=f"{prefix}: {case_type}")
    send_to_project_db(domain, case_type, cases)


def _query_notes(domain):
    schema = DomainSchema(domain).name
    return dedent(
        f"""--
        -- Notes for writing queries against this database:
        --
        -- The search_path is set to this domain's schema ({schema}), so the tables
        -- below can be referenced by their unqualified name.
        --
        -- The following PostgreSQL functions are available:
        --
        --   earth_distance(earth, earth) -> double precision
        --     Great-circle distance in meters between two `earth` points. GPS case
        --     properties are stored in `gps_prop__<name>` columns as `earth` values.
        --     Use ll_to_earth() to build a point to compare against:
        --       SELECT case_id
        --       FROM some_case_type
        --       WHERE earth_distance(gps_prop__location, ll_to_earth(40.7128, -74.006)) < 5000;
        --
        --   ll_to_earth(latitude, longitude) -> earth
        --     Convert a latitude/longitude (in degrees) to an `earth` point.
        --
        --   similarity(text, text) -> real
        --     Trigram similarity between two strings, from 0 (none) to 1 (identical).
        --     Useful for fuzzy matching; higher is a closer match:
        --       SELECT case_id, prop__name
        --       FROM some_case_type
        --       WHERE similarity(prop__name, 'Jon Smith') > 0.3
        --       ORDER BY similarity(prop__name, 'Jon Smith') DESC;
        --
        --   dmetaphone(text) -> text
        --     Double Metaphone phonetic code of a string. Compare codes to match
        --     words that sound alike:
        --       SELECT case_id, prop__name
        --       FROM some_case_type
        --       WHERE dmetaphone(prop__name) = dmetaphone('Catherine');
        --"""
    )


def _describe(domain):
    engine = get_project_db_engine()
    metadata = sqlalchemy.MetaData()
    metadata.reflect(bind=engine, schema=DomainSchema(domain).name)
    if not metadata.tables:
        raise CommandError(f"No project DB tables found for domain '{domain}'")

    print(f"-- Project DB schema for domain: {domain}")
    print(_query_notes(domain))
    with engine.connect() as conn:
        for table in sorted(metadata.tables.values(), key=lambda t: t.name):
            row_count = conn.execute(
                sqlalchemy.select([sqlalchemy.func.count()]).select_from(table)
            ).scalar()
            ddl = str(CreateTable(table).compile(dialect=engine.dialect)).strip()
            print(f"\n-- {row_count} rows")
            print(f"{ddl};")
            for index in table.indexes:
                idx_ddl = str(CreateIndex(index).compile(dialect=engine.dialect)).strip()
                print(f"{idx_ddl};")
