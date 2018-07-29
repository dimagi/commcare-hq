from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application


class Command(AppMigrationCommandBase):
    help = "Migrate single parent index to CaseIndex list in advanced form actions."

    include_builds = False  # AdvancedAction lazy-migrates reverted builds

    def migrate_app(self, app_doc):
        modules = [m for m in app_doc['modules'] if m.get('module_type', '') == 'advanced']
        should_save = False
        for module in modules:
            for form in module['forms']:
                for action_name in form.get('actions', {}):
                    if action_name == 'load_update_cases':
                        for action in form['actions'][action_name]:
                            if 'parent_tag' in action:
                                if action['parent_tag']:
                                    action['case_index'] = {
                                        'tag': action['parent_tag'],
                                        'reference_id': action.get('parent_reference_id', 'parent'),
                                        'relationship': action.get('relationship', 'child'),
                                    }
                                del action['parent_tag']
                                action.pop('parent_reference_id', None)
                                action.pop('relationship', None)
                                should_save = True
                    elif action_name == 'open_cases':
                        for action in form['actions'][action_name]:
                            if 'parent_tag' in action:
                                if action['parent_tag']:
                                    case_index = {
                                        'tag': action['parent_tag'],
                                        'reference_id': action.get('parent_reference_id', 'parent'),
                                        'relationship': action.get('relationship', 'child'),
                                    }
                                    if hasattr(action.get('case_indices'), 'append'):
                                        action['case_indices'].append(case_index)
                                    else:
                                        action['case_indices'] = [case_index]
                                del action['parent_tag']
                                action.pop('parent_reference_id', None)
                                action.pop('relationship', None)
                                should_save = True
        return Application.wrap(app_doc) if should_save else None
