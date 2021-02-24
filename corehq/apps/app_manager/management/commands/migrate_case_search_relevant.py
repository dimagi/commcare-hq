from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)
from corehq.apps.app_manager.util import get_correct_app_class


class Command(AppMigrationCommandBase):
    help = "One-time migration to replace CaseSearch.relevant with default_relevant and additional_relevant"

    chunk_size = 20
    include_builds = True
    include_linked_apps = True

    def migrate_app(self, app_doc):
        default = "count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0"
        prefix = f"({default}) and ("
        should_save = False

        for module in app_doc.get('modules', []):
            if module.get('search_config'):
                relevant = module['search_config'].get('relevant')
                properties = module['search_config'].get('properties')
                default_properties = module['search_config'].get('default_properties')
                if relevant and (properties or default_properties):
                    should_save = True
                    if relevant == default:
                        module['search_config']['default_relevant'] = True
                        module['search_config']['additional_relevant'] = ""
                    elif relevant.startswith(prefix):
                        module['search_config']['default_relevant'] = True
                        module['search_config']['additional_relevant'] = relevant[len(prefix):-1]
                    else:
                        module['search_config']['default_relevant'] = False
                        module['search_config']['additional_relevant'] = relevant
        return get_correct_app_class(app_doc).wrap(app_doc) if should_save else None
