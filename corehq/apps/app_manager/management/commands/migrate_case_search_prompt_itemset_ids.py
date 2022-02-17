import re

from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.fixtures.fixturegenerators import ItemListsProvider


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
                    (new_itemset, should_save) = wrap_itemset(prop.get('itemset'))
                    prop['itemset'] = new_itemset

        return get_correct_app_class(app_doc).wrap(app_doc) if should_save else None


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
