# this has been replaced with custom/benin/management/commands/migrate_users_and_their_cases_to_new_rc_level.py
import math
import os
from datetime import datetime
import itertools
import sqlite3

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs

from corehq.apps.es import UserES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.sql_db.util import paginate_query_across_partitioned_databases
from corehq.util.log import with_progress_bar

from django.db.models import Q

current_time = datetime.now().time()
db_file_path = os.path.expanduser('~/script_items_to_process.db')


class Updater(object):
    chunk_size = 100  # Could potentially increase this
    batch_size = 20000  # Maximum number of cases to process in a single script run
    domain = 'alafiacomm'
    stat_counts = {
        'success': 0,
        'skipped': 0,
        'failed': 0,
    }
    db_table_name = 'default'

    def __init__(self):
        self.db_manager = DBManager(self.db_table_name)


class DBManager(object):

    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILURE = 'failure'
    STATUS_SKIPPED = 'skipped'

    VALID_STATUS = [
        STATUS_PENDING,
        STATUS_SUCCESS,
        STATUS_FAILURE,
        STATUS_SKIPPED,
    ]

    def __init__(self, table_name):
        self.table_name = table_name

    def _get_db_cur(self):
        con = sqlite3.connect(db_file_path)
        return con.cursor()
    
    def setup_db(self):
        cur = self._get_db_cur()
        cur.execute(f"CREATE TABLE {self.table_name} (id, revert_id, status, message)")
        cur.connection.commit()
        cur.close()

    def create_row(self, id):
        # TODO: Catch status that's not pending?
        cur = self._get_db_cur()
        cur.execute(f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?)", (id, '', self.STATUS_PENDING, ''))
        cur.connection.commit()
        cur.close()

    def get_ids(self, count):
        cur = self._get_db_cur()
        res = cur.execute(
            "SELECT id FROM {} WHERE status IN ('{}', '{}')".format(
                self.table_name, self.STATUS_PENDING, self.STATUS_FAILURE
            )
        )
        ids = res.fetchmany(count)
        cur.close()
        flattened_ids = list(itertools.chain.from_iterable(ids))
        return flattened_ids

    def update_row(self, id, value_dict):
        """
        value_dict: Has following format:
        {
            'col_name': 'col_val',
            ...
        }
        Valid column names are revert_id, status, message
        """
        query = f'UPDATE {self.table_name} SET '
        expr_list = []
        for key, val in value_dict.items():
            expr = f"{key} = '{val}'"
            expr_list.append(expr)
        query += ', '.join(expr_list)

        cur = self._get_db_cur()
        cur.execute(f'{query} WHERE id = ?', (id,))
        cur.connection.commit()
        cur.close()


class UserUpdater(Updater):
    rc_num_prop_name = 'rc_number'
    user_type_prop_name = 'usertype'
    db_table_name = 'user_list'

    def store_all_user_ids(self):
        """
        Store all users for later processing. This is useful mainly to store revert_id,
        which can be used to revert changes made. This should be run at the start.
        """
        user_ids = (
            UserES()
            .domain(self.domain)
            .mobile_users()
        ).get_ids()
        for user_id in user_ids:
            self.db_manager.create_row(user_id)

    def start(self, dry_run=False):
        # TODO: Implement code to reverse actions if needed

        print("---MOVING MOBILE WORKER LOCATIONS---")
        # This does not seem right? We should be fetching all ids here?
        user_ids = self.db_manager.get_ids(self.batch_size)
        user_count = len(user_ids)
        chunk_count = math.ceil(user_count / self.batch_size)
        print(f"Total Users to Process: {user_count}")
        print(f"Total Chunks to Process: {chunk_count}")
        user_gen = iter_docs(CommCareUser.get_db(), user_ids)
        for user_chunk in with_progress_bar(chunked(user_gen, self.chunk_size), length=user_count, oneline=False):
            users_to_save, reverse_ids = self._process_chunk(user_chunk)
            is_success = True
            if not dry_run:
                try:
                    CommCareUser.bulk_save(users_to_save)
                except Exception as e:
                    is_success = False
            for user in users_to_save:
                if is_success:
                    self.db_manager.update_row(
                        user.user_id,
                        value_dict={
                            'status': self.db_manager.STATUS_SUCCESS,
                            'revert_id': reverse_ids[user.user_id],
                        }
                    )
                else:
                    self.db_manager.update_row(
                        user.user_id,
                        value_dict={
                            'status': self.db_manager.STATUS_FAILURE,
                            'revert_id': reverse_ids[user.user_id],  # Just in case some users were saved
                            'message': 'Failed to save user in bulk save',
                        }
                    )

        print("Processing Users Complete!")
        print(
            f"Success: {self.stat_counts['success']}, " \
            f"Failed: {self.stat_counts['failed']}, " \
            f"Skipped: {self.stat_counts['skipped']}"
        )

    def _process_chunk(self, user_chunk):
        users_to_save = []
        reverse_ids = {}
        for user in user_chunk:
            user_obj = CommCareUser.wrap(user)
            user_data = user_obj.get_user_data(self.domain)

            # First make sure that the user type is rc
            if (
                self.user_type_prop_name not in user_data
                or user_data[self.user_type_prop_name] != "rc"
            ):
                self.db_manager.update_row(
                    user_obj.user_id, 
                    value_dict={
                        'status': self.db_manager.STATUS_SKIPPED,
                        'message': 'User Type not RC',
                    }
                )
                self.stat_counts['skipped'] += 1
                continue

            if user_obj.location and user_obj.location.name == user_data[self.rc_num_prop_name]:
                # Skip and don't update user if already at location
                self.db_manager.update_row(
                    user_obj.user_id,
                    value_dict={
                        'status': self.db_manager.STATUS_SKIPPED,
                        'message': f'Skipped as user already at RC location with ID {user_obj.location.location_id}'
                    }
                )
                self.stat_counts['skipped'] += 1
                continue

            try:
                # Get a descendant of user location which has the same rc number
                loc = SQLLocation.objects.get(
                    domain=self.domain,
                    parent__location_id=user_obj.location_id,
                    name=user_data[self.rc_num_prop_name]
                )
            except SQLLocation.DoesNotExist as e:
                self.db_manager.update_row(
                    user_obj.user_id,
                    value_dict={
                        'status': self.db_manager.STATUS_FAILURE,
                        'message': f'({user_data[self.rc_num_prop_name]}) does not exist as child of location with id ({user_obj.location_id})'
                    }
                )
                self.stat_counts['failed'] += 1
                continue

            reverse_ids[user_obj.user_id] = user_obj.location_id
            user_obj.location_id = loc.location_id
            self.stat_counts['success'] += 1
            users_to_save.append(user_obj)

        return users_to_save, reverse_ids


class CaseUpdater(Updater):
    device_id = 'system'
    db_table_name_root = 'case_list'

    def __init__(self, case_type):
        """
        case_type: Should be one of [menage, membre, seance_educative, fiche_pointage]
        """
        self.case_type = case_type
        super(CaseUpdater, self).__init__()

    @property
    def db_table_name(self):
        return f'{self.db_table_name_root}_{self.case_type}'

    def _fetch_case_ids(self):
        query = Q(domain=self.domain) & Q(type=self.case_type)
        for row in paginate_query_across_partitioned_databases(CommCareCase, query, values=['case_id'], load_source='all_case_ids'):
            yield row[0]

    def store_all_case_ids(self):
        """
        Fetch all relevant case IDs and store them in a SQLite database for later 
        processing. This should be run once at the start so that we have all the case
        IDs to process. We will retrieve IDs from this DB in chunks
        """
        for id in self._fetch_case_ids():
            self.db_manager.create_row(id)

    def _submit_cases(self, case_blocks):
        submit_case_blocks(
            [cb.as_text() for cb in case_blocks],
            domain=self.domain,
            device_id=self.device_id,
        )

    def start(self, dry_run=False):
        # TODO: Implement code to reverse actions if needed

        print("---MOVING CASE OWNERSHIP---")
        case_ids = self.db_manager.get_ids(self.batch_size)
        case_count = len(case_ids)
        chunk_count = math.ceil(case_count / self.batch_size)
        print(f'Total Cases to Process: {case_count}')
        print(f'Total Chunks to Process: {chunk_count}')
        case_gen = CommCareCase.objects.iter_cases(case_ids, domain=self.domain)
        for case_chunk in with_progress_bar(chunked(case_gen, self.chunk_size), length=case_count, oneline=False):
            cases_to_save, reverse_ids = self._process_chunk(case_chunk)
            if not dry_run:
                self._submit_cases(cases_to_save)
            for case_obj in cases_to_save:
                self.db_manager.update_row(
                    case_obj.case_id,
                    value_dict={
                        'status': self.db_manager.STATUS_SUCCESS,
                        'revert_id': reverse_ids[case_obj.case_id],
                    }
                )
                self.stat_counts['success'] += 1

        print("All Cases Done Processing!")
        print(
            f"Successful: {self.stat_counts['success']}, " \
            f"Failed: {self.stat_counts['failed']}, " \
            f"Skipped: {self.stat_counts['skipped']}"
        )

    def _process_chunk(self, case_chunk):
        cases_to_save = []
        reverse_ids = {}
        for case_obj in case_chunk:
            try:
                user = CommCareUser.get_by_user_id(case_obj.opened_by)
            except CommCareUser.AccountTypeError as e:
                self.db_manager.update_row(
                    case_obj.case_id,
                    value_dict={
                        'status': self.db_manager.STATUS_SKIPPED,
                        'message': 'Not owned by a mobile worker',
                    }
                )
                self.stat_counts['skipped'] += 1
                continue
            
            if user.location_id == case_obj.owner_id:
                # Skip and don't update case if already owned by location
                self.db_manager.update_row(
                    case_obj.case_id,
                    value_dict={
                        'status': self.db_manager.STATUS_SKIPPED,
                        'message': 'Already owned by correct location',
                    }
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

# run this by using the following steps
# case_updater = CaseUpdater('test')
# case_updater.db_manager.setup_db()
# case_updater.store_all_case_ids()
# case_updater.start()
