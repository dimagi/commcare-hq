
from corehq.apps.app_manager.management.commands.helpers import AppMigrationCommandBase
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import wrap_transition_from_old_update_case_action


def get_new_case_update_json(name_path):
    return {
        'question_path': name_path,
        'update_mode': 'always'
    }


class Command(AppMigrationCommandBase):
    help = """
    One-time migration to transition form action models to use ConditionalCaseUpdate as part of the new
    "save only if edited" feature: https://github.com/dimagi/commcare-hq/pull/30910.
    """

    include_linked_apps = True
    include_builds = True

    def migrate_app(self, app_doc):
        for module in app_doc['modules']:
            for form in module['forms']:
                # Normal module
                if module['module_type'] == "basic":
                    actions = form.get('actions', '')
                    if actions:
                        open_case_action = actions.get('open_case', '')
                        update_case_action = actions.get('update_case', '')
                        usercase_update_action = actions.get('usercase_update', '')
                        # Get first elem in subcases list if exists
                        subcases_action = next(iter(actions.get('subcases', '')), None)
                        # Transition form.actions.open_case.update
                        if open_case_action and open_case_action.get('name_path', ''):
                            name_path = open_case_action['name_path']
                            open_case_action['name_update'] = get_new_case_update_json(name_path)
                            del open_case_action['name_path']
                        if update_case_action and update_case_action.get('update', ''):
                            update_case_action['update'] = wrap_transition_from_old_update_case_action(
                                update_case_action['update']
                            )
                        # Transition form.actions.usercase_update.update
                        if usercase_update_action and usercase_update_action.get('update', ''):
                            usercase_update_action['update'] = wrap_transition_from_old_update_case_action(
                                usercase_update_action['update']
                            )
                        if subcases_action:
                            # Transition form.actions.subcases.name_path
                            if subcases_action.get('case_name', ''):
                                case_name = subcases_action['case_name']
                                subcases_action['case_name'] = get_new_case_update_json(case_name)
                                del subcases_action['case_name']
                            # Transition form.actions.subcases.case_properties
                            if subcases_action.get('case_properties', ''):
                                subcases_action['case_properties'] = wrap_transition_from_old_update_case_action(
                                    subcases_action['case_properties'])
                # Advanced module
                elif module['module_type'] == "advanced":
                    for form in module['forms']:
                        if form['form_type'] == 'advanced_form':
                            actions = form.get('actions', '')
                        elif form['form_type'] == 'shadow_form':
                            actions = form.get('extra_actions', '')
                        if actions:
                            open_cases_action = actions.get('open_cases', '')
                            # Get first elem in list if exists
                            load_update_action = next(iter(actions.get('load_update_cases', '')), None)
                            if open_cases_action:
                                # Transition form.actions.open_cases_action.name_path
                                if open_case_action.get('name_path', ''):
                                    name_path = open_case_action['name_path']
                                    open_case_action['name_update'] = get_new_case_update_json(name_path)
                                    del open_case_action['name_path']
                                # Transition form.actions.open_cases_action.case_properties
                                if open_case_action.get('case_properties', ''):
                                    open_case_action['case_properties'] = wrap_transition_from_old_update_case_action(
                                        open_case_action['case_properties'])
                            if load_update_action:
                                # Transition form.actions.load_update_cases.case_properties
                                if load_update_action.get('case_properties', ''):
                                    load_update_action['case_properties'] = wrap_transition_from_old_update_case_action(
                                        load_update_action['case_properties'])
        return Application.wrap(app_doc)
