from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import AdvancedModule, Module, UpdateCaseAction, LoadUpdateAction, \
    FormActionCondition, OpenSubCaseAction, OpenCaseAction, AdvancedOpenCaseAction, Application


class AppFactory(object):
    """
    Example usage:
    >>> factory = AppFactory(build_version='2.11')
    >>> module1, form1 = factory.new_basic_module('open_case', 'house')
    >>> factory.form_opens_case(form1)

    >>> module2, form2 = factory.new_basic_module('update_case', 'person')
    >>> factory.form_updates_case(form2, case_type='house')
    >>> factory.form_opens_case(form2, is_subcase=True)

    >>> module3, form3 = factory.new_advanced_module('advanced', 'person')
    >>> factory.form_updates_case(form3, case_type='house')
    >>> factory.form_updates_case(form3, case_type='person', parent_case_type='house')
    >>> factory.form_opens_case(form3, case_type='child', is_subcase=True)
    """
    def __init__(self, domain='test', name='Untitled Application', version=APP_V2, build_version=None):
        self.app = Application.new_app(domain, name, application_version=version)
        if build_version:
            self.app.build_spec.version = build_version

        self.slugs = {}

    def new_module(self, ModuleClass, slug, case_type, with_form=True):
        if slug in self.slugs:
            raise Exception("duplicate slug")

        module = self.app.add_module(ModuleClass.new_module('{} module'.format(slug), None))
        module.unique_id = '{}_module'.format(slug)
        module.case_type = case_type

        self.slugs[module.unique_id] = slug

        return (module, self.new_form(module)) if with_form else module

    def new_basic_module(self, slug, case_type, with_form=True):
        return self.new_module(Module, slug, case_type, with_form)

    def new_advanced_module(self, slug, case_type, with_form=True):
        return self.new_module(AdvancedModule, slug, case_type, with_form)

    def new_form(self, module):
        slug = self.slugs[module.unique_id]
        form = module.new_form('{} form'.format(slug), lang='en')
        form.unique_id = '{}_form'.format(slug)
        return form

    @staticmethod
    def form_updates_case(form, case_type=None, parent_case_type=None):
        if form.form_type == 'module_form':
            form.requires = 'case'
            form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
            form.actions.update_case.condition.type = 'always'

            if parent_case_type:
                module = form.get_module()
                module.parent_select.active = True
                parent_select_module = next(
                    module for module in module.get_app().get_modules()
                    if module.case_type == parent_case_type
                )
                module.parent_select.module_id = parent_select_module.unique_id
        else:
            case_type = case_type or form.get_module().case_type
            action = LoadUpdateAction(
                case_type=case_type,
                case_tag='load_{}'.format(case_type),
            )

            if parent_case_type:
                parent_action = form.actions.load_update_cases[-1]
                assert parent_action.case_type == parent_case_type
                action.parent_tag = parent_action.case_tag

            form.actions.load_update_cases.append(action)

    @staticmethod
    def form_opens_case(form, case_type=None, is_subcase=False):
        if form.form_type == 'module_form':
            if is_subcase:
                form.actions.subcases.append(OpenSubCaseAction(
                    case_type=case_type,
                    case_name="/data/name",
                    condition=FormActionCondition(type='always')
                ))
            else:
                form.actions.open_case = OpenCaseAction(name_path="/data/name", external_id=None)
                form.actions.open_case.condition.type = 'always'
        else:
            case_type = case_type or form.get_module().case_type
            action = AdvancedOpenCaseAction(
                case_type=case_type,
                case_tag='open_{}'.format(case_type),
                name_path='/data/name'
            )
            if is_subcase:
                action.parent_tag = form.actions.load_update_cases[-1].case_tag

            form.actions.open_cases.append(action)
