import logging
from south.v2 import DataMigration
from dimagi.utils.couch.database import iter_docs
from corehq.apps.app_manager.models import Application
import sys
from django.conf import settings

logger = logging.getLogger(__name__)


class Migration(DataMigration):
    """
    This is the main data migration code for the filter changes.
    """

    def get_all_app_ids(self):
        return {r['id'] for r in Application.get_db().view(
            'app_manager/applications',
            startkey=[None],
            endkey=[None, {}],
            reduce=False,
        ).all()}

    def forwards(self, orm):
        if not settings.UNIT_TESTING:
            errors = []

            def _migrate_app_ids(app_ids):
                to_save = []
                count = len(app_ids)
                logger.info('migrating {} apps'.format(count))
                for i, app_doc in enumerate(iter_docs(Application.get_db(), app_ids)):
                    try:
                        if app_doc["doc_type"] in ["Application", "Application-Deleted"]:
                            application = Application.wrap(app_doc)
                            should_save = self.migrate_app(application)
                            if should_save:
                                to_save.append(application)
                                if len(to_save) > 25:
                                    self.bulk_save(to_save)
                                    to_save = []
                    except Exception, e:
                        errors.append("App {id} not properly migrated because {error}".format(id=app_doc['_id'],
                                                                                              error=sys.exc_info()[0]))
                        raise e

                    if i % 100 == 0 or i == count:
                        logger.info('processed {}/{} apps'.format(i, count))
                if to_save:
                    self.bulk_save(to_save)

            logger.info('migrating applications')
            _migrate_app_ids(self.get_all_app_ids())

            if errors:
                logger.info('\n'.join(errors))

    @classmethod
    def migrate_app(cls, app):
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
                            old_property = axis+"-label-count"
                            new_property = axis+"-labels"
                            count = graph_config.get(old_property, None)
                            if count is not None:
                                graph_config[new_property] = count
                                del graph_config[old_property]
                                needs_save = True
        return needs_save


    @classmethod
    def bulk_save(cls, apps):
        Application.get_db().bulk_save(apps)
        for app in apps:
            logger.info("label-count properties migration on app {id} complete.".format(id=app.id))

    def backwards(self, orm):
        pass

    models = {}
    complete_apps = ['app_manager']
