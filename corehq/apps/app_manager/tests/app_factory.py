from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, UpdateCaseAction, OpenCaseAction


def setup_case_list_form_app():
    app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
    app.build_spec.version = '2.9'

    case_module = app.add_module(Module.new_module('Case module', None))
    case_module.unique_id = 'case_module'
    case_module.case_type = 'suite_test'
    update_case_form = app.new_form(0, 'Update case', lang='en')
    update_case_form.unique_id = 'update_case'
    update_case_form.requires = 'case'
    update_case_form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
    update_case_form.actions.update_case.condition.type = 'always'

    register_module = app.add_module(Module.new_module('register', None))
    register_module.unique_id = 'register_case_module'
    register_module.case_type = case_module.case_type
    register_form = app.new_form(1, 'Register Case Form', lang='en')
    register_form.unique_id = 'register_case_form'
    register_form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
    register_form.actions.open_case.condition.type = 'always'

    case_module.case_list_form.form_id = register_form.get_unique_id()
    case_module.case_list_form.label = {
        'en': 'New Case'
    }
    return app
