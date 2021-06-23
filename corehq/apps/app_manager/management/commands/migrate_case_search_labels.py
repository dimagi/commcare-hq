from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)
from corehq.apps.app_manager.util import get_correct_app_class


class Command(AppMigrationCommandBase):
    help = "One-time migration to replace CaseSearch command_label and again_label with " \
           "search_label and search_again_label"

    chunk_size = 1
    include_builds = True
    include_linked_apps = True

    def migrate_app(self, app_doc):
        should_save = False
        for module in app_doc.get('modules', []):
            if module.get('search_config'):
                command_label = module['search_config'].get('command_label')
                search_label_label = module['search_config'].get('search_label', {}).get('label')
                # if there is some value set for old label but nothing has been set for new label yet
                if command_label and not search_label_label:
                    should_save = True
                    module['search_config']['search_label'] = {'label': command_label}

                again_label = module['search_config'].get('again_label')
                search_again_label_label = module['search_config'].get('search_again_label', {}).get('label')
                # if there is some value set for old label but nothing has been set for new label yet
                if again_label and not search_again_label_label:
                    should_save = True
                    module['search_config']['search_again_label'] = {'label': again_label}

        return get_correct_app_class(app_doc).wrap(app_doc) if should_save else None
