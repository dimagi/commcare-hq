import uuid

from corehq.apps.app_manager.const import AUTO_SELECT_USERCASE
from corehq.apps.app_manager.models import (
    AdvancedForm,
    AdvancedModule,
    AdvancedOpenCaseAction,
    Application,
    AutoSelectCase,
    CaseIndex,
    CaseSearchProperty,
    ConditionalCaseUpdate,
    DetailColumn,
    FormActionCondition,
    LoadUpdateAction,
    Module,
    OpenCaseAction,
    OpenSubCaseAction,
    PreloadAction,
    ReportModule,
    ShadowModule,
    UpdateCaseAction,
)
from corehq.apps.app_manager.tests.util import get_build_spec_for_tests


class AppFactory(object):
    """
    Example usage:
    >>> factory = AppFactory(build_version='2.11.0')
    >>> module1, form1 = factory.new_basic_module('open_case', 'house')
    >>> factory.form_opens_case(form1)

    >>> module2, form2 = factory.new_basic_module('update_case', 'person')
    >>> factory.form_requires_case(form2, case_type='house')
    >>> factory.form_opens_case(form2, is_subcase=True)

    >>> module3, form3 = factory.new_advanced_module('advanced', 'person')
    >>> factory.form_requires_case(form3, case_type='house')
    >>> factory.form_requires_case(form3, case_type='person', parent_case_type='house')
    >>> factory.form_opens_case(form3, case_type='child', is_subcase=True)
    """

    def __init__(self, domain='test', name='Untitled Application', build_version=None, include_xmlns=False):
        self.app = Application.new_app(domain, name)
        self.app.build_spec = get_build_spec_for_tests(build_version)

        self.slugs = {}
        self.include_xmlns = include_xmlns

    def get_form(self, module_index, form_index):
        return self.app.get_module(module_index).get_form(form_index)

    def new_module(self, ModuleClass, slug, case_type, with_form=True, parent_module=None, case_list_form=None):
        if slug in self.slugs:
            raise Exception("duplicate slug")

        module = self.app.add_module(ModuleClass.new_module('{} module'.format(slug), None))
        module.unique_id = '{}_module'.format(slug)
        module.case_type = case_type

        if parent_module:
            module.root_module_id = self.unique_id(parent_module)

        if case_list_form:
            module.case_list_form.form_id = self.unique_id(case_list_form)

        self.slugs[module.unique_id] = slug

        return (module, self.new_form(module)) if with_form else module

    def new_basic_module(self, slug, case_type, with_form=True, parent_module=None, case_list_form=None):
        return self.new_module(Module, slug, case_type, with_form, parent_module, case_list_form)

    def new_advanced_module(self, slug, case_type, with_form=True, parent_module=None, case_list_form=None):
        return self.new_module(AdvancedModule, slug, case_type, with_form, parent_module, case_list_form)

    def new_shadow_module(self, slug, source_module, with_form=True, shadow_module_version=2, parent_module=None):
        module = self.app.add_module(ShadowModule.new_module('{} module'.format(slug), None))
        module.unique_id = '{}_module'.format(slug)
        module.source_module_id = source_module.unique_id
        if parent_module:
            module.root_module_id = self.unique_id(parent_module)
        module.shadow_module_version = shadow_module_version
        self.slugs[module.unique_id] = slug
        return (module, self.new_form(module)) if with_form else module

    def new_report_module(self, slug, parent_module=None):
        return self.new_module(ReportModule, slug, None, with_form=False, parent_module=parent_module)

    def new_form(self, module):
        slug = self.slugs[module.unique_id]
        index = len(module.forms)
        form = module.new_form('{} form {}'.format(slug, index), None, '')
        form.unique_id = '{}_form_{}'.format(slug, index)
        form.source = ''  # set form source since we changed the unique_id
        if self.include_xmlns:
            form.xmlns = "http://openrosa.org/formdesigner/{}".format(uuid.uuid4().hex)
        return form

    def new_shadow_form(self, module):
        slug = self.slugs[module.unique_id]
        index = len(module.forms)
        form = module.new_shadow_form('{} form {}'.format(slug, index), None)
        form.unique_id = '{}_form_{}'.format(slug, index)
        return form

    def unique_id(self, module_or_form):
        return module_or_form if isinstance(module_or_form, str) else module_or_form.unique_id

    @staticmethod
    def form_requires_case(form, case_type=None, parent_case_type=None, update=None, preload=None):
        if update:
            update = {
                name: ConditionalCaseUpdate(question_path=question_path) for name, question_path in update.items()}
        if form.form_type == 'module_form':
            form.requires = 'case'
            if update:
                form.actions.update_case = UpdateCaseAction(update=update)
                form.actions.update_case.condition.type = 'always'
            if preload:
                form.actions.case_preload = PreloadAction(preload=preload)
                form.actions.case_preload.condition.type = 'always'

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
            index = len([load for load in form.actions.load_update_cases if load.case_type == case_type])
            kwargs = {'case_type': case_type, 'case_tag': 'load_{}_{}'.format(case_type, index)}
            if update:
                kwargs['case_properties'] = update
            if preload:
                kwargs['preload'] = preload
            action = LoadUpdateAction(**kwargs)

            if parent_case_type:
                parent_action = form.actions.load_update_cases[-1]
                assert parent_action.case_type == parent_case_type
                action.case_index = CaseIndex(tag=parent_action.case_tag)

            form.actions.load_update_cases.append(action)

    @staticmethod
    def form_opens_case(form, case_type=None, is_subcase=False, parent_tag=None, is_extension=False):
        if form.form_type == 'module_form':
            if is_subcase:
                form.actions.subcases.append(OpenSubCaseAction(
                    case_type=case_type,
                    name_update=ConditionalCaseUpdate(question_path="/data/name"),
                    condition=FormActionCondition(type='always')
                ))
            else:
                form.actions.open_case = OpenCaseAction(
                    name_update=ConditionalCaseUpdate(question_path="/data/name"),
                    external_id=None
                )
                form.actions.open_case.condition.type = 'always'
        else:
            case_type = case_type or form.get_module().case_type
            action = AdvancedOpenCaseAction(
                case_type=case_type,
                case_tag='open_{}'.format(case_type),
                name_update=ConditionalCaseUpdate(question_path='/data/name'),
            )
            if is_subcase:
                if not parent_tag:
                    parent_tag = form.actions.load_update_cases[-1].case_tag

                action.case_indices = [CaseIndex(
                    tag=parent_tag,
                    relationship='extension' if is_extension else 'child'
                )]

            form.actions.open_cases.append(action)

    @staticmethod
    def form_uses_usercase(form, update=None, preload=None):
        if form.form_type == 'module_form':
            if update:
                form.actions.usercase_update = UpdateCaseAction(update=update)
                form.actions.usercase_update.condition.type = 'always'
            if preload:
                form.actions.usercase_preload = PreloadAction(preload=preload)
                form.actions.usercase_preload.condition.type = 'always'
        else:
            AppFactory.advanced_form_autoloads(form, AUTO_SELECT_USERCASE, None)

    @staticmethod
    def form_workflow(form, mode):
        form.post_form_workflow = mode

    @classmethod
    def case_list_form_app_factory(cls):
        factory = cls(build_version='2.9.0')

        case_module, update_case_form = factory.new_basic_module('case_module', 'suite_test')
        factory.form_requires_case(update_case_form)

        register_module, register_form = factory.new_basic_module('register_case', 'suite_test')
        factory.form_opens_case(register_form)

        case_module.case_list_form.form_id = register_form.get_unique_id()
        case_module.case_list_form.label = {
            'en': 'New Case',
        }
        return factory

    @classmethod
    def case_claim_app_factory(cls):
        factory = cls(build_version='2.51.0')

        case_module, update_case_form = factory.new_basic_module('case_module', 'suite_test')

        register_module, register_form = factory.new_basic_module('register_case', 'suite_test')
        factory.form_opens_case(register_form)

        case_module.case_list_form.form_id = register_form.get_unique_id()
        case_module.case_list_form.label = {
            'en': 'New Case',
        }
        case_module.search_config.search_label.label = {
            'en': 'Find a Mother',
        }
        case_module.search_config.search_again_label.label = {
            'en': 'Find Another Mother',
        }
        case_module.search_config.title_label = {
            'en': 'Find a Mom',
        }
        case_module.search_config.description = {
            'en': 'More information',
        }

        case_module.search_config.properties = [CaseSearchProperty(
            name='name',
            label={'en': 'Name of Mother'}
        )]
        return factory

    @staticmethod
    def advanced_form_autoloads(form, mode, value_key, value_source=None):
        """See corehq.apps.app_manager.models.AutoSelectCase
        """
        assert isinstance(form, AdvancedForm)
        form.actions.load_update_cases.append(LoadUpdateAction(
            case_tag='auto_select_{}'.format(mode),
            auto_select=AutoSelectCase(
                mode=mode,
                value_source=value_source,
                value_key=value_key
            )
        ))

    @staticmethod
    def add_module_case_detail_column(module, display, field, trans, lang='en'):
        assert display in ('short', 'long')
        details = module.case_details.long if display == 'long' else module.case_details.short
        details.columns.append(DetailColumn(
            format='plain',
            field=field,
            header={lang: trans},
            model='case',
        ))
