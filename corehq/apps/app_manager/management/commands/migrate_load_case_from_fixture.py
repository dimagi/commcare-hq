from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application


class Command(AppMigrationCommandBase):
    help = "Migrate load case from fixture to enable more general usage"

    include_builds = True

    def migrate_app(self, app_doc):
        modules = [m for m in app_doc['modules'] if m.get('module_type', '') == 'advanced']
        should_save = False
        for module in modules:
            for form in module['forms']:
                load_actions = form.get('actions', {}).get('load_update_cases', [])
                for action in load_actions:
                    if action['load_case_from_fixture'] is not None:
                        old_fixture_variable = action['load_case_from_fixture']['fixture_variable']
                        if old_fixture_variable.startswith("./@"):
                            # Assume that this means this was already migrated
                            continue
                        action['load_case_from_fixture']['fixture_variable'] = "./@{}".format(old_fixture_variable)
                        should_save = True

        return Application.wrap(app_doc) if should_save else None
