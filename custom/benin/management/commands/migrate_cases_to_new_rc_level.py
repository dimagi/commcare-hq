import math
import os

from django.core.management.base import BaseCommand
from django.db.models import Q

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.models import CommCareCase
from corehq.sql_db.util import (
    paginate_query,
    paginate_query_across_partitioned_databases,
)
from corehq.util.log import with_progress_bar
from custom.benin.management.commands.base import DBManager, Updater

sqlite_db_file_path = os.path.expanduser('~/migrate_cases_to_new_rc_level.db')
sqlite_db_table_name_prefix = "cases"


class Command(BaseCommand):
    help = 'Migrate benin project\'s cases to new rc level locations'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('domain')
        parser.add_argument(
            'case_type',
            help="Case type on the domain to migrate for"
        )
        parser.add_argument(
            '--db_name',
            help='Django DB alias to run on'
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            default=False,
            help="A dry run to only share the updates that would happen",
        )

    def handle(self, domain, case_type, **options):
        dry_run = options['dry_run']
        db_alias = options['db_name']

        table_name = f"{sqlite_db_table_name_prefix}_{case_type}"
        if db_alias:
            table_name += f"_{db_alias}"
        db_manager = DBManager(sqlite_db_file_path, table_name)
        case_updater = CaseUpdater(domain, case_type, db_manager, db_alias)

        print("Fetching updated users location id.")
        updated_users_location_ids = load_updated_users_location_ids()
        print("Finished loading user details")

        response = input("Print user details? (y/n)")
        if response == 'y':
            for user_id, location_id in updated_users_location_ids.items():
                print(f"{user_id}: {location_id}: {SQLLocation.active_objects.get(location_id).name}")

        print("Fetching all case ids.")
        if db_alias:
            print(f"Using only db: {db_alias}")

        case_ids = case_updater.store_all_case_ids()
        print(f"Stored {len(case_ids)}.")

        print("Iterating cases now...")
        case_updater.start(updated_users_location_ids, dry_run)


class CaseUpdater(Updater):
    device_id = 'system'

    def __init__(self, domain, case_type, db_manager, db_alias):
        """
        case_type: Should be one of [menage, membre, seance_educative, fiche_pointage]
        """
        self.case_type = case_type
        self.db_alias = db_alias
        super(CaseUpdater, self).__init__(domain, db_manager)

    def _fetch_case_ids(self):
        query = Q(domain=self.domain) & Q(type=self.case_type)
        if self.db_alias:
            for row in paginate_query(self.db_alias, CommCareCase, query, values=['case_id'],
                                      load_source='all_case_ids'):
                yield row[0]
        else:
            for row in paginate_query_across_partitioned_databases(CommCareCase, query, values=['case_id'],
                                                                   load_source='all_case_ids'):
                yield row[0]

    def store_all_case_ids(self):
        """
        Fetch all relevant case IDs and store them in a SQLite database for later
        processing. This should be run once at the start so that we have all the case
        IDs to process. We will retrieve IDs from this DB in chunks
        """
        for id in self._fetch_case_ids():
            self.db_manager.create_row(id)

        return self.db_manager.get_ids()

    def _submit_cases(self, case_blocks):
        submit_case_blocks(
            [cb.as_text() for cb in case_blocks],
            domain=self.domain,
            device_id=self.device_id,
        )

    def start(self, updated_users_location_ids, dry_run=False):
        # TODO: Implement code to reverse actions if needed
        if not dry_run:
            print("---MOVING CASE OWNERSHIP---")
        else:
            print("---FETCHING EXPECTED UPDATES FOR CASES---")

        case_ids = self.db_manager.get_ids()

        case_count = len(case_ids)
        chunk_count = math.ceil(case_count / self.chunk_size)
        print(f'Total Cases to Process: {case_count}')
        print(f"Batch size: {self.chunk_size}")
        print(f'Total Batches to Process: {chunk_count}')

        response = input("Do you want to proceed? (y/n)")
        if not response == 'y':
            print("Process aborted. Bye!")
            exit(0)

        cases_docs_gen = CommCareCase.objects.iter_cases(case_ids, domain=self.domain)
        for cases in (
            with_progress_bar(
                chunked(cases_docs_gen, self.chunk_size),
                length=case_count,
                oneline=False)
        ):
            case_blocks, reverse_ids = self._process_chunk(cases, updated_users_location_ids)
            if not dry_run:
                print("Updating cases...")
                self._submit_cases(case_blocks)
                print("Updated cases!")
            for case_block in case_blocks:
                self._save_row(
                    case_id=case_block.case_id,
                    status=self.db_manager.STATUS_SUCCESS,
                    message='',
                    revert_id=reverse_ids[case_block.case_id],
                    updated_id=case_block.owner_id
                )
                self.stat_counts['success'] += 1

        print("All Cases Done Processing!")
        print(
            f"Successful: {self.stat_counts['success']}, "
            f"Failed: {self.stat_counts['failed']}, "
            f"Skipped: {self.stat_counts['skipped']}"
        )

    def _process_chunk(self, cases, updated_users_location_ids):
        cases_to_save = []
        reverse_ids = {}
        for case_obj in cases:
            if case_obj.opened_by in updated_users_location_ids:
                updated_location_id = updated_users_location_ids[case_obj.opened_by]
            else:
                self._save_row(
                    case_obj.case_id,
                    status=self.db_manager.STATUS_SKIPPED,
                    message=f'Could not find mobile worker {case_obj.opened_by}'
                )
                self.stat_counts['skipped'] += 1
                continue

            if updated_location_id == case_obj.owner_id:
                # Skip and don't update case if already owned by location
                self._save_row(
                    case_id=case_obj.case_id,
                    status=self.db_manager.STATUS_SKIPPED,
                    message='Already owned by correct location'

                )
                self.stat_counts['skipped'] += 1
                continue

            case_block = CaseBlock(
                create=False,
                case_id=case_obj.case_id,
                owner_id=updated_location_id,
            )
            reverse_ids[case_obj.case_id] = case_obj.owner_id
            cases_to_save.append(case_block)

        return cases_to_save, reverse_ids

    def _save_row(self, case_id, status, message, revert_id=None, updated_id=None):
        value_dict = {
            'status': status,
            'message': message
        }
        if revert_id:
            value_dict['revert_id'] = revert_id
        if updated_id:
            value_dict['updated_id'] = updated_id

        self.db_manager.update_row(
            case_id,
            value_dict=value_dict
        )


def load_updated_users_location_ids():
    updated_users_location_ids = {}
    from custom.benin.management.commands.migrate_users_to_new_rc_level import (
        sqlite_db_file_path as user_sqlite_db_file_path,
        sqlite_db_table_name as user_sqlite_db_table_name)
    user_db_manager = DBManager(user_sqlite_db_file_path, user_sqlite_db_table_name)
    cur = user_db_manager._get_db_cur()
    res = cur.execute(
        "SELECT id, update_id FROM {} WHERE status = '{}'".format(
            user_sqlite_db_table_name, user_db_manager.STATUS_SUCCESS
        )
    )
    result = res.fetchall()
    cur.close()
    for user_id, updated_location_id in result:
        updated_users_location_ids[user_id] = updated_location_id
    validate_location_ids_loaded(updated_users_location_ids)
    return updated_users_location_ids


def validate_location_ids_loaded(updated_users_location_ids):
    location_ids = updated_users_location_ids.values()
    locations = SQLLocation.active_objects.get_locations(location_ids)
    assert len(location_ids) == len(locations), "Locations loaded for users incorrectly"
