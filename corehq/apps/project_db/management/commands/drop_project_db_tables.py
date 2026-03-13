import sqlalchemy

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.project_db.schema import (
    get_project_db_engine,
    get_project_db_table_name,
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

        engine = get_project_db_engine()
        metadata = sqlalchemy.MetaData()
        tables = []
        for case_type in case_type_names:
            name = get_project_db_table_name(domain, case_type)
            try:
                tables.append(
                    sqlalchemy.Table(name, metadata, autoload_with=engine)
                )
            except sqlalchemy.exc.NoSuchTableError:
                pass

        if not tables:
            self.stdout.write("No project DB tables found for this domain.")
            return

        self.stdout.write(f"Tables to drop ({len(tables)}):")
        for table in tables:
            self.stdout.write(f"  - {table.name}")

        confirm = input("\nType 'yes' to confirm: ")
        if confirm != 'yes':
            self.stdout.write("Aborted.")
            return

        for table in tables:
            table.drop(engine)
            self.stdout.write(f"  Dropped {table.name}")

        self.stdout.write(
            self.style.SUCCESS(f"Dropped {len(tables)} tables.")
        )
