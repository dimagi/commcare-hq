from datetime import timedelta
import logging
from collections import namedtuple
from time import time

from django.core.management import BaseCommand

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
            '--use-chunks',
            action='store_true',
            default=False,
            help='''To break up this management command across multiple chunks of domains to make it executable
            over a large number of domains, set this to true and use the 'chunk-number' and 'total-chunks'
            variables. Assumes that the result of get_domains() is ordered and constant between command
            executions.''',
        )
        parser.add_argument(
            '--total-chunks',
            action='store',
            default=None,
            help='''Specify the total number of chunks to break the list of domains into. 'use-chunks' must be
            true.''',
        )
        parser.add_argument(
            '--chunk-number',
            action='store',
            default=None,
            help='''Specify which domain list chunk number you would like to perform this command on.
            Start at one.''',
        )

    def handle(self, **options):
        start_time = time()
        self.options = options
        if self.options['domain']:
            domains = [self.options['domain']]
        elif self.use_chunks:
            num_domains = len(self.get_domains())
            start_at = int(num_domains * (self.chunk_number - 1) / self.total_chunks)
            end_at = int(num_domains * self.chunk_number / self.total_chunks)
            domains = self.get_domains()[start_at:end_at] or [None]
            logger.info(f'''{num_domains} total domains. Beginning at domain #{start_at},\
                            ending at domain #{end_at}.''')
        else:
            domains = self.get_domains() or [None]
        for domain in domains:
            app_ids = self.get_app_ids(domain)
            logger.info('migrating {} apps{}'.format(len(app_ids), f" in {domain}" if domain else ""))
            iter_update(Application.get_db(), self._migrate_app, app_ids, verbose=True, chunksize=self.chunk_size)
        end_time = time()
        execution_time_seconds = end_time - start_time
        logger.info(f"Completed in {timedelta(seconds=execution_time_seconds)}.")

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
    def use_chunks(self):
        return self.options.get('use_chunks', False)

    @property
    def total_chunks(self):
        return int(self.options.get('total_chunks', None))

    @property
    def chunk_number(self):
        return int(self.options.get('chunk_number', None))

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
