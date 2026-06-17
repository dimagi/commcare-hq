from django.core.management.base import BaseCommand, CommandError

import dateutil.parser

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.project_db.populate import send_to_project_db
from corehq.apps.project_db.table_ddl import (
    DomainSchema,
    create_or_update_project_db,
    get_project_db_engine,
)
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseReindexAccessor,
    iter_all_rows,
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

    def handle(self, domain, sync, drop, populate, since, **options):
        if drop and (sync or populate):
            raise CommandError("--drop cannot be combined with --sync or --populate.")
        if since and not populate:
            raise CommandError("--since is only used in conjunction with --populate.")

        if sync:
            create_or_update_project_db(domain)
            self.stdout.write("Synced ProjectDB table definition")
        if populate:
            _populate(domain, since)
            self.stdout.write("Populated ProjectDB")
        if drop:
            with get_project_db_engine().begin() as conn:
                DomainSchema(domain).drop(conn)
            self.stdout.write("Deleted ProjectDB table")


def _populate(domain, start_date):
    case_types = CaseType.objects.filter(
        domain=domain,
        is_deprecated=False
    ).values_list('name', flat=True)

    for case_type in case_types:
        _populate_case_type(domain, case_type, start_date)


def _populate_case_type(domain, case_type, start_date):
    accessor = CaseReindexAccessor(domain=domain, case_type=case_type, start_date=start_date)
    cases = iter_all_rows(accessor)
    send_to_project_db(domain, case_type, cases)
