from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)
from corehq.apps.app_manager.util import get_correct_app_class


class Command(AppMigrationCommandBase):
    help = "One-time migration to replace CaseSearch command_label and again_label with " \
           "search_label and search_again_label"

    chunk_size = 20
    include_builds = True
    include_linked_apps = True

    def migrate_app(self, app_doc):
        should_save = False
        for module in app_doc.get('modules', []):
            if module.get('search_config'):
                command_label = module['search_config'].get('command_label')
                if command_label != module['search_config']['search_label']['label']:
                    should_save = True
                    module['search_config']['search_label']['label'] = command_label

                again_label = module['search_config'].get('again_label')
                if again_label != module['search_config']['search_again_label']['label']:
                    should_save = True
                    module['search_config']['search_again_label']['label'] = again_label

        return get_correct_app_class(app_doc).wrap(app_doc) if should_save else None
