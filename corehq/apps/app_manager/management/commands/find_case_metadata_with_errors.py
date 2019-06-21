from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application

logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


def log_excessive_parents(app, action):
    hierarchy = action.split('/')
    if len(hierarchy) > 3:
        logger.error('%s,%s,%s', app.domain, app._id, action)


class Command(AppMigrationCommandBase):
    help = "find case errrors"

    include_builds = False

    def migrate_app(self, app_doc):
        app = Application.wrap(app_doc)
        metadata = app.get_case_metadata()
        for case_type in metadata.case_types:
            if case_type.has_errors:
                logger.error('app {} has issue'.format(app._id))
        for module in app.modules:
            for form in module.forms:
                if form.doc_type == 'AdvancedForm' or form.doc_type == 'ShadowForm':
                    # advanced forms don't have the same actions
                    return None
                actions = form.actions
                if actions.case_preload:
                    for action in actions.case_preload.preload.values():
                        log_excessive_parents(app, action)
                if actions.update_case:
                    for action in actions.update_case.update:
                        log_excessive_parents(app, action)
        return None
