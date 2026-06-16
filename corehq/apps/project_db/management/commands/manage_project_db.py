from django.core.management.base import BaseCommand, CommandError

from corehq.apps.project_db.table_ddl import (
    DomainSchema,
    create_or_update_project_db,
    get_project_db_engine,
)


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
            help="Drop the domain's ProjectDB schema.",
        )

    def handle(self, domain, sync, drop, **options):
        if drop and sync:
            raise CommandError("--drop cannot be combined with --sync")

        if sync:
            create_or_update_project_db(domain)
            self.stdout.write(f"Synced ProjectDB table definition")
        if drop:
            with get_project_db_engine().begin() as conn:
                DomainSchema(domain).drop(conn)
            self.stdout.write(f"Deleted ProjectDB table")
