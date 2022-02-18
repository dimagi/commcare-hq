import re

from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)
from corehq.apps.fixtures.fixturegenerators import ItemListsProvider
from corehq.toggles import SYNC_SEARCH_CASE_CLAIM


class Command(AppMigrationCommandBase):
    help = "One-time migration to add 'item-list:' prefix to instance ids in case search itemset prompts"

    chunk_size = 1
    include_builds = True
    include_linked_apps = True

    def migrate_app(self, app_doc):
        should_save = False
        for module in app_doc.get('modules', []):
            if module.get('search_config'):
                properties = module.get('search_config').get('properties')
                if not isinstance(properties, list):
                    continue
                for prop in properties:
                    (new_itemset, updated) = wrap_itemset(prop.get('itemset'))
                    should_save = should_save or updated
                    prop['itemset'] = new_itemset

        return app_doc if should_save else None

    def get_domains(self):
        return sorted(SYNC_SEARCH_CASE_CLAIM.get_enabled_domains())


def wrap_itemset(data):
    if data is None:
        return None, False

    should_save = False
    if (data.get('instance_uri') or '').startswith(f'jr://fixture/{ItemListsProvider.id}:'):
        instance_id = data.get('instance_id')
        if instance_id and ItemListsProvider.id not in instance_id:
            should_save = True
            data['instance_id'] = f'{ItemListsProvider.id}:{instance_id}'
            data['nodeset'] = re.sub(r"instance\((.)" + instance_id,
                                     r"instance(\1" + ItemListsProvider.id + r":" + instance_id,
                                     (data.get('nodeset') or ''))

    return data, should_save
