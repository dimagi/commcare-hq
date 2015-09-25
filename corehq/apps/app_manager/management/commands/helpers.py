from collections import namedtuple
import logging
from optparse import make_option
from couchdbkit.exceptions import BulkSaveError
from django.core.management import BaseCommand
from corehq.apps.app_manager.models import Application
from dimagi.utils.couch.database import iter_docs

logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


def get_all_app_ids(include_builds=False):
    key = [None]
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
    option_list = BaseCommand.option_list + (
        make_option('--failfast',
                    action='store_true',
                    dest='failfast',
                    default=False,
                    help='Stop processing if there is an error'),
    )

    def handle(self, *args, **options):
        self.options = options

        def _migrate_app_ids(app_ids):
            to_save = []
            count = len(app_ids)
            logger.info('migrating {} apps'.format(count))
            for i, app_doc in enumerate(iter_docs(Application.get_db(), app_ids)):
                try:
                    if app_doc["doc_type"] in ["Application", "Application-Deleted"]:
                        migrated_app = self.migrate_app(app_doc)
                        if migrated_app:
                            to_save.append(migrated_app)
                            if len(to_save) > 25:
                                self.bulk_save(to_save)
                                to_save = []
                except Exception, e:
                    logger.exception("App {id} not properly migrated".format(id=app_doc['_id']))
                    if options['failfast']:
                        raise e

                if i % 100 == 0 or i == count:
                    logger.info('processed {}/{} apps'.format(i, count))
            if to_save:
                self.bulk_save(to_save)

        logger.info('migrating applications')
        _migrate_app_ids(self.get_app_ids())
        logger.info('done')

    def get_app_ids(self):
        return get_all_app_ids(self.include_builds)

    def migrate_app(self, app):
        raise NotImplementedError()

    def bulk_save(self, apps):
        def log_success(app_ids):
            for app_id in app_ids:
                logger.info("Migration on app {id} complete.".format(id=app_id))

        try:
            Application.get_db().bulk_save(apps)
            log_success(app.id for app in apps)
        except BulkSaveError as e:
            log_success(result.id for result in e.results if getattr(result, 'ok', False))
            errors = [SaveError(**error) for error in e.errors]
            handled = self.handle_save_errors(errors)
            if not handled and self.options['failfast']:
                raise e

    def handle_save_errors(self, errors):
        """
        Override this to do custom error handling.
        :param errors:  list of SaveError tuples
        :return:        True if the error has been handled and should not cause the migration to stop
        """
        logger.error("Doc save errors: %s", errors)
        return False
