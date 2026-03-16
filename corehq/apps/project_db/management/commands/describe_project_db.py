import sqlalchemy
from sqlalchemy.schema import CreateIndex, CreateTable

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.project_db.schema import (
    get_project_db_engine,
    get_schema_name,
)


class Command(BaseCommand):
    help = (
        "Describe a domain's project DB schema. Outputs DDL suitable "
        "for feeding to an LLM to construct SQL queries."
    )

    def add_arguments(self, parser):
        parser.add_argument('domain', help="The project domain to describe.")

    def handle(self, domain, **options):
        engine = get_project_db_engine()
        schema_name = get_schema_name(domain)

        metadata = sqlalchemy.MetaData()
        metadata.reflect(bind=engine, schema=schema_name)
        if not metadata.tables:
            raise CommandError(
                f"No project DB tables found for domain '{domain}'."
            )

        self.stdout.write(f"-- Project DB schema for domain: {domain}")
        self.stdout.write(f"-- Tables are queryable by case type name with:")
        self.stdout.write(f"--   SET LOCAL search_path TO \"{schema_name}\";")
        self.stdout.write("")

        for table in sorted(metadata.tables.values(), key=lambda t: t.name):
            ddl = CreateTable(table).compile(dialect=engine.dialect)
            self.stdout.write(f"{ddl}".strip() + ";")
            for index in table.indexes:
                idx_ddl = CreateIndex(index).compile(dialect=engine.dialect)
                self.stdout.write(f"{idx_ddl}".strip() + ";")
            self.stdout.write("")
