import math
import os

from django.core.management.base import BaseCommand
from django.db.models import Q

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
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

        print("Fetching all case ids.")
        if db_alias:
            print(f"Using only db: {db_alias}")

        case_ids = case_updater.store_all_case_ids()
        print(f"Stored {len(case_ids)}.")

        print("Iterating cases now...")
        case_updater.start(dry_run)


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

    def start(self, dry_run=False):
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
            case_blocks, reverse_ids = self._process_chunk(cases)
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
                )
                self.stat_counts['success'] += 1

        print("All Cases Done Processing!")
        print(
            f"Successful: {self.stat_counts['success']}, "
            f"Failed: {self.stat_counts['failed']}, "
            f"Skipped: {self.stat_counts['skipped']}"
        )

    def _process_chunk(self, cases):
        cases_to_save = []
        reverse_ids = {}
        for case_obj in cases:
            try:
                user = CommCareUser.get_by_user_id(case_obj.opened_by)
            except CommCareUser.AccountTypeError:
                self._save_row(
                    case_obj.case_id,
                    status=self.db_manager.STATUS_SKIPPED,
                    message='Not owned by a mobile worker'
                )
                self.stat_counts['skipped'] += 1
                continue

            if user.location_id == case_obj.owner_id:
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
                owner_id=user.location_id,
            )
            reverse_ids[case_obj.case_id] = case_obj.owner_id
            cases_to_save.append(case_block)

        return cases_to_save, reverse_ids

    def _save_row(self, case_id, status, message, revert_id=None):
        value_dict = {
            'status': status,
            'message': message
        }
        if revert_id:
            value_dict['revert_id'] = revert_id

        self.db_manager.update_row(
            case_id,
            value_dict=value_dict
        )
