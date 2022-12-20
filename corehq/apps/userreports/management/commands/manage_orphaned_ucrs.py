from collections import defaultdict

from django.core.management.base import BaseCommand

from corehq.apps.userreports.dbaccessors import (
    drop_ucr_tables,
    get_deletable_ucrs,
    get_orphaned_tables_by_engine_id,
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
            '--force-delete',
            action='store_true',
            default=False,
            help='Drop orphaned tables on active domains'
        )
        parser.add_argument(
            '--domain',
            action='store',
            help='Drop orphaned tables for a specific domain'
        )

    def handle(self, **options):
        orphaned_tables_by_engine_id = get_orphaned_tables_by_engine_id(options.get('engine_id'))
        try:
            ucrs_to_delete = get_deletable_ucrs(orphaned_tables_by_engine_id, force_delete=options['force_delete'],
                                                domain=options['domain'])
        except AssertionError as e:
            suggestions = """
            Use the '--domain' option to further inspect a specific domain.
            Use the '--force-delete' option if you are sure you want to
            delete all orphaned ucrs.
            """
            print(str(e))
            print(suggestions)
            exit(0)

        log_orphaned_tables(ucrs_to_delete)

        if options.get('command') == CMD_DELETE and confirm_deletion_with_user():
            tablenames = get_tables_names(ucrs_to_delete)
            drop_ucr_tables(tablenames)


def log_orphaned_tables(ucrs_to_delete):
    if not ucrs_to_delete:
        print("Did not find any orphaned UCRs.")
        return

    for engine_id, ucr_infos in ucrs_to_delete.items():
        if len(ucr_infos) > 0:
            print(f"Found orphaned UCRs in the {engine_id} database:")
            for ucr_info in ucr_infos:
                print(
                    f"\t{ucr_info['tablename']}, {ucr_info['row_count']} rows."
                )
        else:
            print(f"Did not find orphaned UCRs in the {engine_id} database.")


def get_tables_names(ucrs_to_delete):
    tablenames_to_drop = defaultdict(list)
    for engine_id, ucr_infos in ucrs_to_delete.items():
        for ucr_info in ucr_infos:
            tablenames_to_drop[engine_id].append(ucr_info['tablename'])

    return tablenames_to_drop


def confirm_deletion_with_user():
    return input("Are you sure you want to delete orphaned UCRs? (y/n)") == 'y'
