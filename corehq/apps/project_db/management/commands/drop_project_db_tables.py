import sqlalchemy

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.project_db.schema import (
    get_project_db_engine,
    get_schema_name,
)


class Command(BaseCommand):
    help = "Drop all project DB tables for a domain."

    def add_arguments(self, parser):
        parser.add_argument('domain', help="The project domain.")

    def handle(self, domain, **options):
        case_type_names = list(
            CaseType.objects.filter(domain=domain)
            .values_list('name', flat=True)
            .order_by('name')
        )
        if not case_type_names:
            raise CommandError(
                f"No case types found for domain '{domain}'."
            )

        schema_name = get_schema_name(domain)
        engine = get_project_db_engine()

        # Check if the schema exists
        inspector = sqlalchemy.inspect(engine)
        if schema_name not in inspector.get_schema_names():
            self.stdout.write(
                f"Schema \"{schema_name}\" does not exist. Nothing to drop."
            )
            return

        # List tables in the schema
        table_names = inspector.get_table_names(schema=schema_name)
        if not table_names:
            self.stdout.write(
                f"Schema \"{schema_name}\" exists but has no tables."
            )
            return

        self.stdout.write(f"Tables in \"{schema_name}\" ({len(table_names)}):")
        for name in sorted(table_names):
            self.stdout.write(f"  - {name}")

        confirm = input("\nType 'yes' to drop schema and all tables: ")
        if confirm != 'yes':
            self.stdout.write("Aborted.")
            return

        with engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP SCHEMA "{schema_name}" CASCADE'
            ))

        self.stdout.write(
            self.style.SUCCESS(
                f"Dropped schema \"{schema_name}\" "
                f"with {len(table_names)} tables."
            )
        )
