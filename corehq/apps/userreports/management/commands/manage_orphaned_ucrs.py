from django.core.management.base import BaseCommand

from corehq.apps.userreports.dbaccessors import (
    drop_orphaned_ucrs,
    get_all_data_sources,
    get_orphaned_ucrs,
)

CMD_FIND = 'find'
CMD_DELETE = 'delete'
CMD_CHOICES = [CMD_FIND, CMD_DELETE]


class Command(BaseCommand):
    """
    An orphaned UCR table is one where the related datasource no longer exists
    This command is designed to find and/or delete orphaned UCRs
    """
    help = "Find and/or delete orphaned UCR tables"

    def add_arguments(self, parser):
        parser.add_argument('command', choices=CMD_CHOICES)
        parser.add_argument(
            '--engine_id',
            action='store',
            help='Only check this DB engine',
        )
        parser.add_argument(
            '--ignore-active-domains',
            action='store',
            default=True,
            help='If True, only includes orphaned UCRs from deleted domains.'
        )
        parser.add_argument(
            '--domain',
            action='store',
            help='Drop orphaned tables for a specific domain'
        )

    def handle(self, **options):
        command = options.get('command')
        domain = options.get('domain')

        engine_ids = {ds.engine_id for ds in get_all_data_sources()}
        for engine_id in engine_ids:
            try:
                orphaned_ucrs = get_orphaned_ucrs(
                    engine_id,
                    domain=domain,
                    ignore_active_domains=options.get('ignore_active_domains'))
            except AssertionError as e:
                print(str(e))
                continue

            if not orphaned_ucrs:
                print(f"Did not find orphaned UCRs in the {engine_id} db.")
                continue

            print(f"Found the following orphaned UCRs in the {engine_id} db:")
            for ucr in orphaned_ucrs:
                print(f"\t{ucr}")

            if command == CMD_DELETE and confirm_deletion_with_user():
                drop_orphaned_ucrs(engine_id, orphaned_ucrs)


def confirm_deletion_with_user():
    return input("Are you sure you want to delete orphaned UCRs? (y/n)") == 'y'
