import re

from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)
from corehq.toggles import USH_INLINE_SEARCH

results_instance_re = re.compile(r"""instance\(['"]results['"]\)""", re.UNICODE)
input_instance_re = re.compile(r"""instance\(['"]search-input:results['"]\)""", re.UNICODE)
new_instance = "search_results"
results_new = f"instance('{new_instance}')"
input_new = f"instance('search-input:{new_instance}')"


class Command(AppMigrationCommandBase):
    help = """"""

    chunk_size = 1
    include_builds = True
    include_linked_apps = True

    def migrate_app(self, app_doc):
        should_save = False
        for module in app_doc.get('modules', []):
            search_config = module.get('search_config')
            if (
                search_config
                and search_config.get('properties')
                and search_config.get('auto_launch')
                and search_config.get('inline_search')
            ):
                should_save |= self._migrate_detail(app_doc, module, 'short')
                should_save |= self._migrate_detail(app_doc, module, 'long')

        return app_doc if should_save else None

    def get_domains(self):
        return sorted(USH_INLINE_SEARCH.get_enabled_domains())

    def _migrate_detail(self, app, module, detail):
        details = module.get('case_details').get(detail)
        should_save = False
        for col in details.get('columns'):
            field = col.get('field')
            new_field = results_instance_re.sub(results_new, field)
            new_field = input_instance_re.sub(input_new, new_field)
            if field != new_field:
                should_save = True
                col['field'] = new_field
                if self.log_debug:
                    print("    ", field, "-->", new_field)

        if should_save and self.log_info:
            name = module['name'].get('en', module['name'])
            print(f"Updated {detail} details for module '{name}' in app: {app['_id']}")
        return should_save
