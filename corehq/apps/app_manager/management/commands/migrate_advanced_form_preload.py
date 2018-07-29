from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application


class Command(AppMigrationCommandBase):
    help = "Migrate preload dict in advanced forms to " \
           "allow loading the same case property into multiple questions."

    include_builds = False

    def migrate_app(self, app_doc):
        modules = [m for m in app_doc['modules'] if m.get('module_type', '') == 'advanced']
        should_save = False
        for module in modules:
            forms = module['forms']
            for form in forms:
                load_actions = form.get('actions', {}).get('load_update_cases', [])
                for action in load_actions:
                    preload = action['preload']
                    if preload and list(preload.values())[0].startswith('/'):
                        action['preload'] = {v: k for k, v in preload.items()}
                        should_save = True

        return Application.wrap(app_doc) if should_save else None
