from datetime import timedelta
import logging
from collections import namedtuple
from time import time

from django.core.management import BaseCommand
from django.db import models

from corehq.apps.app_manager.models import Application
from corehq.util.couch import DocUpdate, iter_update

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


SaveError = namedtuple('SaveError', 'id error reason')


APP_MIGRATION_CMD_DOMAIN_LIST_POSITION = 0

def get_domain_list_position():
    return APP_MIGRATION_CMD_DOMAIN_LIST_POSITION

def increment_domain_list_position():
    global APP_MIGRATION_CMD_DOMAIN_LIST_POSITION
    APP_MIGRATION_CMD_DOMAIN_LIST_POSITION += 1

def reset_domain_list_position():
    global APP_MIGRATION_CMD_DOMAIN_LIST_POSITION
    APP_MIGRATION_CMD_DOMAIN_LIST_POSITION = 0

class AppMigrationCommandBase(BaseCommand):
    """
    Base class for commands that want to migrate apps.
    """
    chunk_size = 100
    include_builds = False
    include_linked_apps = False

    options = {}

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
            '--restartable',
            action='store_true',
            default=False,
            help='''If restarted, the command will continue at the place in the domains list where it left off 
            when it was cancelled. This option is 'True' by default. Restartability does not persist through 
            different Django instances. Should not be used with a single domain.''',
        )

    def handle(self, **options):
        start_time = time()
        self.options = options
        if self.options['domain']:
            domains = [self.options['domain']]
        elif self.restartable:
            domains = self.get_domains()[get_domain_list_position():] or [None]
        else:
            domains = self.get_domains() or [None]
        for domain in domains:
            print(f'domain pos: {get_domain_list_position()}')
            app_ids = self.get_app_ids(domain)
            logger.info('migrating {} apps{}'.format(len(app_ids), f" in {domain}" if domain else ""))
            iter_update(Application.get_db(), self._migrate_app, app_ids, verbose=True, chunksize=self.chunk_size)
            if self.restartable:
                increment_domain_list_position()
        end_time = time()
        execution_time_seconds = end_time - start_time
        logger.info(f"Completed in {timedelta(seconds=execution_time_seconds)}.")
        if self.restartable:
            reset_domain_list_position()

    @property
    def is_dry_run(self):
        return self.options.get('dry_run', False)

    @property
    def log_info(self):
        return self.options.get("verbosity", 0) > 1

    @property
    def log_debug(self):
        return self.options.get("verbosity", 0) > 2

    @property
    def restartable(self):
         return self.options.get('restartable', False)

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
        if not getattr(app_doc, 'copy_of', False) and getattr(app_doc, 'version', False):
            app_doc['version'] = app_doc['version'] + 1
        return app_doc

    def get_app_ids(self, domain=None):
        return get_all_app_ids(domain=domain, include_builds=self.include_builds)

    def get_domains(self):
        return None

    def migrate_app(self, app):
        """Return the app dict if the doc is to be saved else None"""
        raise NotImplementedError()
