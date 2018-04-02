from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
import logging
from django.core.management import BaseCommand
from corehq.apps.app_manager.models import Application
from corehq.util.couch import iter_update, DocUpdate

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
    include_builds = False

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

    def handle(self, **options):
        self.options = options
        app_ids = self.get_app_ids()
        logger.info('migrating {} apps'.format(len(app_ids)))
        results = iter_update(Application.get_db(), self._migrate_app, app_ids, verbose=True)
        self.results_callback(results)
        logger.info('done')

    def _migrate_app(self, app_doc):
        try:
            if app_doc["doc_type"] in ["Application", "Application-Deleted"]:
                migrated_app = self.migrate_app(app_doc)
                if migrated_app:
                    return DocUpdate(migrated_app)
        except Exception as e:
            logger.exception("App {id} not properly migrated".format(id=app_doc['_id']))
            if self.options['failfast']:
                raise e

    def get_app_ids(self):
        return get_all_app_ids(domain=self.options.get('domain', None), include_builds=self.include_builds)

    def migrate_app(self, app):
        raise NotImplementedError()

    def results_callback(self, results):
        """
        Override this to do custom result handling.
        :param results:  an object with the following properties:
                        'ignored_ids', 'not_found_ids', 'deleted_ids', 'updated_ids', 'error_ids'
        """
        pass
