from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)


class Command(AppMigrationCommandBase):
    help = """
    Short-lived command from 2023-03-02 to fix unwrappable apps caused by
    removing an overridden wrap method before it had been applied. The scope is
    believed to be small, so this approach is preferable to re-migrating
    everything.
    https://dimagi-dev.atlassian.net/jira/servicedesk/projects/SUPPORT/queues/custom/125/SUPPORT-16128
    https://dimagi-dev.atlassian.net/browse/SUPPORT-16045
    """
    chunk_size = 5
    DOMAIN_LIST_FILENAME = 'fix_unwrappable_apps-domains.txt'
    DOMAIN_PROGRESS_NUMBER_FILENAME = 'fix_unwrappable_apps-progress.txt'

    def migrate_app(self, app_doc):
        changed = False
        for i, module in enumerate(app_doc['modules']):
            if 'search_config' in module:
                for prop in module['search_config']['properties']:
                    required = prop.get('required')
                    if required and isinstance(required, str):
                        prop['required'] = {'test': required}
                        changed = True

                    old_validations = prop.pop('validation', None)  # it was changed to plural
                    if old_validations:
                        prop['validations'] = [{
                            'test': old['xpath'],
                            'text': old['message'],
                        } for old in old_validations if old.get('xpath')]
                        changed = True

        wrap_app(app_doc)  # this will be logged if it raises an exception

        if changed:
            return app_doc
