import logging
from optparse import make_option
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


def bulk_save(apps):
    Application.get_db().bulk_save(apps)
    for app in apps:
        logger.info("Migration on app {id} complete.".format(id=app.id))


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
                                bulk_save(to_save)
                                to_save = []
                except Exception, e:
                    logger.exception("App {id} not properly migrated".format(id=app_doc['_id']))
                    if options['failfast']:
                        raise e

                if i % 100 == 0 or i == count:
                    logger.info('processed {}/{} apps'.format(i, count))
            if to_save:
                bulk_save(to_save)

        logger.info('migrating applications')
        _migrate_app_ids(self.get_app_ids())
        logger.info('done')

    def get_app_ids(self):
        return get_all_app_ids(self.include_builds)

    def migrate_app(self, app):
        raise NotImplementedError()
