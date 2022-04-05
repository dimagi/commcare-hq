import logging
from collections import namedtuple

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
        if self.options['domain']:
            domains = [self.options['domain']]
        else:
            domains = self.get_domains() or [None]
        for domain in domains:
            app_ids = self.get_app_ids(domain)
            logger.info('migrating {} apps{}'.format(len(app_ids), f" in {domain}" if domain else ""))
            iter_update(Application.get_db(), self._migrate_app, app_ids, verbose=True, chunksize=self.chunk_size)
        logger.info('done')

    def _doc_types(self):
        doc_types = ["Application", "Application-Deleted"]
        if self.include_linked_apps:
            doc_types.extend(["LinkedApplication", "LinkedApplication-Deleted"])
        return doc_types

    def _migrate_app(self, app_doc):
        try:
            if app_doc["doc_type"] in self._doc_types():
                migrated_app = self.migrate_app(app_doc)
                if migrated_app:
                    return DocUpdate(migrated_app)
        except Exception as e:
            logger.exception("App {id} not properly migrated".format(id=app_doc['_id']))
            if self.options['failfast']:
                raise e

    def get_app_ids(self, domain=None):
        return get_all_app_ids(domain=domain, include_builds=self.include_builds)

    def get_domains(self):
        return None

    def migrate_app(self, app):
        raise NotImplementedError()
