import math
import os

from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs

from corehq.apps.es import UserES
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.user_data import prime_user_data_caches
from corehq.util.log import with_progress_bar
from custom.benin.management.commands.base import DBManager, Updater

db_file_path = os.path.expanduser('~/migrate_users_to_new_rc_level.db')
db_table_name = "users"


class Command(BaseCommand):
    help = 'Migrate benin project\'s users to new rc level locations.'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('domain')
        parser.add_argument(
            '--dry_run',
            action='store_true',
            default=False,
            help="A dry run to only share the updates that would happen",
        )

    def handle(self, domain, **options):
        dry_run = options['dry_run']

        db_manager = DBManager(db_file_path, db_table_name)
        user_updater = UserUpdater(domain, db_manager)

        print("Fetching all user ids.")
        user_ids = user_updater.store_all_user_ids()
        print(f"Stored {len(user_ids)}.")

        print("Iterating users now...")
        user_updater.start(dry_run)


class UserUpdater(Updater):

    def store_all_user_ids(self):
        """
        Store all users for later processing. This is useful mainly to store revert_id,
        which can be used to revert changes made. This should be run at the start.
        """
        user_ids = (
            UserES()
            .domain(self.domain)
            .mobile_users()
            .is_active()
        ).get_ids()
        for user_id in user_ids:
            self.db_manager.create_row(user_id)
        return user_ids

    def start(self, dry_run=False):
        # TODO: Implement code to reverse actions if needed
        if not dry_run:
            print("---MOVING MOBILE WORKER LOCATIONS---")
        else:
            print("---FETCHING EXPECTED UPDATES FOR USERS---")

        user_ids = self.db_manager.get_ids()

        user_count = len(user_ids)
        chunks_count = math.ceil(user_count / self.chunk_size)
        print(f"Users to Process: {user_count}")
        print(f"Batch size: {self.chunk_size}")
        print(f"Total batches to Process: {chunks_count}")

        response = input("Do you want to proceed? (y/n)")
        if not response == 'y':
            exit(0)

        users_docs_gen = iter_docs(CommCareUser.get_db(), user_ids)
        for user_chunk in (
            with_progress_bar(
                chunked(users_docs_gen, self.chunk_size),
                length=user_count,
                oneline=False
            )
        ):
            users = [CommCareUser.wrap(user_doc) for user_doc in user_chunk]
            users_to_save, reverse_ids = self._process_chunk(users)
            is_success = True
            if not dry_run:
                try:
                    CommCareUser.bulk_save(users_to_save)
                except Exception as e:
                    is_success = False
                    print(f"Failed to bulk save users: {e}")
            for user in users_to_save:
                if is_success:
                    self._save_row(
                        user_id=user.user_id,
                        status=self.db_manager.STATUS_SUCCESS,
                        message='',
                        revert_id=reverse_ids[user.user_id]
                    )
                else:
                    self._save_row(
                        user_id=user.user_id,
                        status=self.db_manager.STATUS_FAILURE,
                        message='Failed to save user in bulk save',
                        revert_id=reverse_ids[user.user_id]
                    )

        print("Processing Users Complete!")
        print(
            f"Success: {self.stat_counts['success']}, "
            f"Failed: {self.stat_counts['failed']}, "
            f"Skipped: {self.stat_counts['skipped']}"
        )

    def _process_chunk(self, users):
        users_to_save = []
        reverse_ids = {}
        rc_num_prop_name = 'rc_number'
        user_type_prop_name = 'usertype'

        users = prime_user_data_caches(users, self.domain)

        for user in users:
            user_data = user.get_user_data(self.domain)

            # First make sure that the user type is rc
            if (
                user_type_prop_name not in user_data
                or user_data[user_type_prop_name] != "rc"
            ):
                self._save_row(
                    user_id=user.user_id,
                    status=self.db_manager.STATUS_SKIPPED,
                    message='User Type not RC'
                )
                self.stat_counts['skipped'] += 1
                continue

            if user.location and user.location.name == user_data[rc_num_prop_name]:
                # Skip and don't update user if already at location
                self._save_row(
                    user_id=user.user_id,
                    status=self.db_manager.STATUS_SKIPPED,
                    message=f'Skipped as user already at RC location with ID {user.location.location_id}'
                )
                self.stat_counts['skipped'] += 1
                continue

            try:
                # Get a descendant of user location which has the same rc number
                loc = SQLLocation.objects.get(
                    domain=self.domain,
                    parent__location_id=user.location_id,
                    name=user_data[rc_num_prop_name]
                )
            except SQLLocation.DoesNotExist:
                self._save_row(
                    user_id=user.user_id,
                    status=self.db_manager.STATUS_FAILURE,
                    message=f'({user_data[rc_num_prop_name]}) does not exist '
                            f'as child of location with id ({user.location_id})'
                )
                self.stat_counts['failed'] += 1
                continue

            reverse_ids[user.user_id] = user.location_id
            user.location_id = loc.location_id
            self.stat_counts['success'] += 1
            users_to_save.append(user)

        return users_to_save, reverse_ids

    def _save_row(self, user_id, status, message, revert_id=None):
        value_dict = {
            'status': status,
            'message': message
        }
        if revert_id:
            value_dict['revert_id'] = revert_id

        self.db_manager.update_row(
            user_id,
            value_dict=value_dict
        )
