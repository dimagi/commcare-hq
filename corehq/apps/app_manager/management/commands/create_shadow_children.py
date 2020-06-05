from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)
from corehq.apps.app_manager.models import Application, ShadowModule


class Command(AppMigrationCommandBase):
    help = "Create explicit child modules for shadow modules whose source is a parent"

    def migrate_app(self, app_doc):
        source_module_ids = {
            m['source_module_id']: m['unique_id']
            for m in app_doc['modules'] if m.get('module_type', '') == 'shadow'
        }
        child_modules_of_shadows = [
            m for m in app_doc['modules'] if m['root_module_id'] in source_module_ids
        ]
        if not child_modules_of_shadows:
            return

        app = Application.wrap(app_doc)
        for child_module in child_modules_of_shadows:
            new_shadow = ShadowModule.new_module(child_module['name']['en'], 'en')
            new_shadow.source_module_id = child_module['unique_id']
            new_shadow.root_module_id = source_module_ids[child_module['root_module_id']]
            new_shadow.put_in_root = child_module['put_in_root']
            app.add_module(new_shadow)

        app.move_child_modules_after_parents()  # TODO: probably shouldn't do this blindly
        return app
