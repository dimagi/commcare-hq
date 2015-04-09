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
        _migrate_app_ids(get_all_app_ids(self.include_builds))
        logger.info('done')

    def migrate_app(self, app):
        raise NotImplementedError()


class Command(AppMigrationCommandBase):
    help = "Migrate all graph configuration 'x-label-count' and " \
           "'y-label-count' properties to 'x-labels' and 'y-labels'"

    include_builds = True

    def migrate_app(self, app_doc):
        print app_doc['_id']
        raise Exception()
        app = Application.wrap(app_doc)
        needs_save = False
        for module in app.get_modules():
            for detail_type in ["case_details", "task_details", "goal_details", "product_details"]:
                details = getattr(module, detail_type, None)
                if details is None:
                    # This module does not have the given detail_type
                    continue
                for detail in [details.short, details.long]:
                    for column in detail.get_columns():
                        graph_config = getattr(getattr(column, "graph_configuration", None), "config", {})
                        for axis in ["x", "y"]:
                            old_property = axis + "-label-count"
                            new_property = axis + "-labels"
                            count = graph_config.get(old_property, None)
                            if count is not None:
                                graph_config[new_property] = count
                                del graph_config[old_property]
                                needs_save = True

        return app if needs_save else None
