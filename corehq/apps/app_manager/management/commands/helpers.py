from datetime import timedelta
import logging
from collections import namedtuple
import os
from time import time

from django.core.management import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.domain_migration_flags.api import (
    ALL_DOMAINS,
    migration_in_progress,
    set_migration_complete,
    set_migration_started,
    get_migration_complete
)
from corehq.util.couch import DocUpdate, get_db_by_doc_type, iter_update

logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


def get_all_app_ids(domain=None, include_builds=False):
    key = [domain]
    if not include_builds:
        key += [None]

    return {r['id'] for r in Application.get_db().view(
        'app_manager/applications',
        startkey=key,
        endkey=key + [{}],
        reduce=False,
    ).all()}


def get_deleted_app_ids(domain=None):
    db = get_db_by_doc_type('Application')
    return (get_doc_ids_in_domain_by_type(domain, 'Application-Deleted', database=db)
        + get_doc_ids_in_domain_by_type(domain, 'LinkedApplication-Deleted', database=db)
        + get_doc_ids_in_domain_by_type(domain, 'RemoteApp-Deleted', database=db))


SaveError = namedtuple('SaveError', 'id error reason')


class AppMigrationCommandBase(BaseCommand):
    """
    Base class for commands that want to migrate apps.
    """
    chunk_size = 100
    include_builds = True
    include_linked_apps = False

    options = {}

    DOMAIN_LIST_FILENAME = None
    DOMAIN_PROGRESS_NUMBER_FILENAME = None

    def add_arguments(self, parser):
        parser.add_argument(
            '--failfast',
            action='store_true',
            dest='failfast',
            default=False,
            help='Stop processing if there is an error',
        )
        parser.add_argument(
            '--domain',
            help='Migrate only this domain',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help="Perform the migration but don't save any changes",
        )
        parser.add_argument(
            '--start-from-scratch',
            action='store_true',
            default=False,
            help="If existing progress files for this command exist, turn this flag on to ignore them and start"
                 "from scratch.",
        )
        parser.add_argument(
            '--force-run-again',
            action='store_true',
            default=False,
            help='''By default, this migration will not run a second time once it has been run. This flag forces
                    the migration to run a second time, even if it has been run before on the environment.''',
        )

    def handle(self, **options):
        self.options = options

        if not self.options.get('force_run_again', False) and not self.is_dry_run:
            self.command_name = self.__module__[self.__module__.rindex('.') + 1:]
            if get_migration_complete(ALL_DOMAINS, self.command_name):
                logger.info("This migration command has already been run on this environment. Exiting...")
                return
            elif not migration_in_progress(ALL_DOMAINS, self.command_name):
                set_migration_started(ALL_DOMAINS, self.command_name)

        self.start_time = time()
        self.check_filenames_set()

        if self.options['domain']:
            domains = [self.options['domain']]
            domain_list_position = 0
        else:
            can_continue_progress, domain_list_position, domains = self.try_to_continue_progress()
            if can_continue_progress:
                domains = domains[domain_list_position:]
            else:
                domains = self.get_domains() or [None]
                self.store_domain_list(domains)
        for domain in domains:
            app_ids = self.get_app_ids(domain)
            logger.info('migrating {} apps{}'.format(len(app_ids), f" in {domain}" if domain else ""))
            iter_update(Application.get_db(), self._migrate_app, app_ids, verbose=True, chunksize=self.chunk_size)
            domain_list_position = self.increment_progress(domain_list_position)
        self.end_migration()

    @property
    def is_dry_run(self):
        return self.options.get('dry_run', False)

    @property
    def log_info(self):
        return self.options.get("verbosity", 0) > 1

    @property
    def log_debug(self):
        return self.options.get("verbosity", 0) > 2

    def _doc_types(self):
        doc_types = ["Application", "Application-Deleted"]
        if self.include_linked_apps:
            doc_types.extend(["LinkedApplication", "LinkedApplication-Deleted"])
        return doc_types

    def _migrate_app(self, app_doc):
        try:
            if app_doc["doc_type"] in self._doc_types():
                migrated_app = self.migrate_app(app_doc)
                if migrated_app and not self.is_dry_run:
                    return DocUpdate(self.increment_app_version(migrated_app))
        except Exception as e:
            logger.exception("App {id} not properly migrated".format(id=app_doc['_id']))
            if self.options['failfast']:
                raise e

    @staticmethod
    def increment_app_version(app_doc):
        try:
            copy_of = app_doc['copy_of']
            version = app_doc['version']
        except KeyError:
            return
        if not copy_of and version:
            app_doc['version'] = version + 1
        return app_doc

    def get_app_ids(self, domain=None):
        return (list(get_deleted_app_ids(domain))
                + list(get_all_app_ids(domain=domain, include_builds=self.include_builds)))

    def get_domains(self):
        return None

    def migrate_app(self, app):
        """Return the app dict if the doc is to be saved else None"""
        raise NotImplementedError()

    def check_filenames_set(self):
        if not self.DOMAIN_LIST_FILENAME or not self.DOMAIN_PROGRESS_NUMBER_FILENAME:
            raise Exception("You must set filenames that track progress on the domain list for this command.")

    def increment_progress(self, domain_list_position):
        logger.info(f"Migrated domain #{domain_list_position}")
        domain_list_position += 1
        with open(self.DOMAIN_PROGRESS_NUMBER_FILENAME, 'w') as f:
            f.write(str(domain_list_position))
        return domain_list_position

    def store_domain_list(self, domains):
        with open(self.DOMAIN_LIST_FILENAME, 'w') as f:
            f.writelines(f'{domain}\n' for domain in domains)

    def try_to_continue_progress(self):
        if not self.options['start_from_scratch']:
            try:
                with open(self.DOMAIN_PROGRESS_NUMBER_FILENAME, 'r') as f:
                    domain_list_position = int(f.readline())
                with open(self.DOMAIN_LIST_FILENAME, 'r') as f:
                    domains = []
                    for line in f:
                        domains.append(line.strip())
                logger.info(f"Continuing migration progress at domain number {domain_list_position}...")
                return True, domain_list_position, domains
            except FileNotFoundError:
                logger.info("Domain progress file(s) not found. Starting from scratch...")
        return False, 0, None

    def remove_storage_files(self):
        try:
            os.remove(self.DOMAIN_LIST_FILENAME)
            os.remove(self.DOMAIN_PROGRESS_NUMBER_FILENAME)
        except FileNotFoundError:
            pass

    def end_migration(self):
        self.remove_storage_files()
        end_time = time()
        execution_time_seconds = end_time - self.start_time

        if (not self.is_dry_run and not self.options.get('force_run_again', False)
           and migration_in_progress(ALL_DOMAINS, self.command_name)):
            set_migration_complete(ALL_DOMAINS, self.command_name)

        logger.info(f"Completed in {timedelta(seconds=execution_time_seconds)}.")
