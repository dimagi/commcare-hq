from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2, AUTO_SELECT_USERCASE
from corehq.apps.app_manager.models import Application, Module, UpdateCaseAction, OpenCaseAction, PreloadAction, \
    WORKFLOW_MODULE, AdvancedModule, AdvancedOpenCaseAction, LoadUpdateAction, AutoSelectCase, OpenSubCaseAction, \
    FormActionCondition
from corehq.apps.app_manager.tests.util import TestFileMixin
from mock import patch


class CaseListFormSuiteTests(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'case_list_form')

    def _prep_case_list_form_app(self):
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

    def test_case_list_registration_form(self):
        app = self._prep_case_list_form_app()
        case_module = app.get_module(0)
        case_module.case_list_form.media_image = 'jr://file/commcare/image/new_case.png'
        case_module.case_list_form.media_audio = 'jr://file/commcare/audio/new_case.mp3'
        self.assertXmlEqual(self.get_xml('case-list-form-suite'), app.create_suite())

    def test_case_list_registration_form_usercase(self):
        app = self._prep_case_list_form_app()
        register_module = app.get_module(1)
        register_form = register_module.get_form(0)
        register_form.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'question1'})
        register_form.actions.usercase_preload.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('case-list-form-suite-usercase'), app.create_suite())

    def test_case_list_registration_form_end_for_form_nav(self):
        app = self._prep_case_list_form_app()
        app.build_spec.version = '2.9'
        registration_form = app.get_module(1).get_form(0)
        registration_form.post_form_workflow = WORKFLOW_MODULE

        self.assertXmlPartialEqual(
            self.get_xml('case-list-form-suite-form-nav-entry'),
            app.create_suite(),
            "./entry[2]"
        )

    def test_case_list_registration_form_no_media(self):
        app = self._prep_case_list_form_app()

        self.assertXmlPartialEqual(
            self.get_xml('case-list-form-suite-no-media-partial'),
            app.create_suite(),
            "./detail[@id='m0_case_short']/action"
        )

    def test_case_list_form_multiple_modules(self):
        app = self._prep_case_list_form_app()
        case_module1 = app.get_module(0)

        case_module2 = app.add_module(Module.new_module('update2', None))
        case_module2.unique_id = 'update case 2'
        case_module2.case_type = case_module1.case_type
        update2 = app.new_form(2, 'Update Case Form2', lang='en')
        update2.unique_id = 'update_case_form2'
        update2.requires = 'case'
        update2.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        update2.actions.update_case.condition.type = 'always'

        case_module2.case_list_form.form_id = 'register_case_form'
        case_module2.case_list_form.label = {
            'en': 'New Case'
        }

        self.assertXmlEqual(
            self.get_xml('case-list-form-suite-multiple-references'),
            app.create_suite(),
        )

    def test_case_list_registration_form_advanced(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        app.build_spec.version = '2.9'

        register_module = app.add_module(AdvancedModule.new_module('create', None))
        register_module.unique_id = 'register_module'
        register_module.case_type = 'dugong'
        register_form = app.new_form(0, 'Register Case', lang='en')
        register_form.unique_id = 'register_case_form'
        register_form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type='dugong',
            case_tag='open_dugong',
            name_path='/data/name'
        ))

        case_module = app.add_module(AdvancedModule.new_module('update', None))
        case_module.unique_id = 'case_module'
        case_module.case_type = 'dugong'
        update_form = app.new_form(1, 'Update Case', lang='en')
        update_form.unique_id = 'update_case_form'
        update_form.actions.load_update_cases.append(LoadUpdateAction(
            case_type='dugong',
            case_tag='load_dugong',
            details_module=case_module.unique_id
        ))

        case_module.case_list_form.form_id = register_form.get_unique_id()
        case_module.case_list_form.label = {
            'en': 'Register another Dugong'
        }
        self.assertXmlEqual(self.get_xml('case-list-form-advanced'), app.create_suite())

    def test_case_list_registration_form_advanced_autoload(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        app.build_spec.version = '2.9'

        register_module = app.add_module(AdvancedModule.new_module('create', None))
        register_module.unique_id = 'register_module'
        register_module.case_type = 'dugong'
        register_form = app.new_form(0, 'Register Case', lang='en')
        register_form.unique_id = 'register_case_form'
        register_form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type='dugong',
            case_tag='open_dugong',
            name_path='/data/name'
        ))
        register_form.actions.load_update_cases.append(LoadUpdateAction(
            case_tag='usercase',
            auto_select=AutoSelectCase(
                mode=AUTO_SELECT_USERCASE,
            )
        ))

        case_module = app.add_module(AdvancedModule.new_module('update', None))
        case_module.unique_id = 'case_module'
        case_module.case_type = 'dugong'
        update_form = app.new_form(1, 'Update Case', lang='en')
        update_form.unique_id = 'update_case_form'
        update_form.actions.load_update_cases.append(LoadUpdateAction(
            case_type='dugong',
            case_tag='load_dugong',
            details_module=case_module.unique_id
        ))

        case_module.case_list_form.form_id = register_form.get_unique_id()
        case_module.case_list_form.label = {
            'en': 'Register another Dugong'
        }
        self.assertXmlEqual(self.get_xml('case-list-form-advanced-autoload'), app.create_suite())

    def test_case_list_form_parent_child_advanced(self):
        """
        * Register house (case type = house, basic)
          * Register house form
        * Register person (case type = person, parent select = 'Register house', advanced)
          * Register person form
        * Manager person (case type = person, case list form = 'Register person form', basic)
          * Manage person form
        """
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        app.build_spec.version = '2.9'

        register_house_module = app.add_module(Module.new_module('create house', None))
        register_house_module.unique_id = 'register_house_module'
        register_house_module.case_type = 'house'
        register_house_form = app.new_form(0, 'Register House', lang='en')
        register_house_form.unique_id = 'register_house_form'
        register_house_form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        register_house_form.actions.open_case.condition.type = 'always'

        register_person_module = app.add_module(AdvancedModule.new_module('create person', None))
        register_person_module.unique_id = 'register_person_module'
        register_person_module.case_type = 'person'
        register_person_form = app.new_form(1, 'Register Person', lang='en')
        register_person_form.unique_id = 'register_person_form'
        register_person_form.actions.load_update_cases.append(LoadUpdateAction(
            case_type='house',
            case_tag='load_house',
            details_module=register_house_module.unique_id
        ))
        register_person_form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type='person',
            case_tag='open_person',
            parent_tag='load_house',
            name_path='/data/name'
        ))

        person_module = app.add_module(Module.new_module('Manage person', None))
        person_module.unique_id = 'manage_person'
        person_module.case_type = 'person'

        person_module.case_list_form.form_id = register_person_form.unique_id

        person_module.parent_select.active = True
        person_module.parent_select.module_id = register_house_module.unique_id
        update_person_form = app.new_form(2, 'Update person', lang='en')
        update_person_form.unique_id = 'update_person_form'
        update_person_form.requires = 'case'
        update_person_form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        update_person_form.actions.update_case.condition.type = 'always'

        self.assertXmlEqual(self.get_xml('case-list-form-suite-parent-child-advanced'), app.create_suite())

    def test_case_list_form_parent_child_basic(self):
        """
        * Register house (case type = house, basic)
          * Register house form
        * Register person (case type = person, parent select = 'Register house', basic)
          * Register person form
        * Manager person (case type = person, case list form = 'Register person form', basic)
          * Manage person form
        """
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        app.build_spec.version = '2.9'

        register_house_module = app.add_module(Module.new_module('create house', None))
        register_house_module.unique_id = 'register_house_module'
        register_house_module.case_type = 'house'
        register_house_form = app.new_form(0, 'Register House', lang='en')
        register_house_form.unique_id = 'register_house_form'
        register_house_form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        register_house_form.actions.open_case.condition.type = 'always'

        register_person_module = app.add_module(Module.new_module('create person', None))
        register_person_module.unique_id = 'register_person_module'
        register_person_module.case_type = 'house'
        register_person_form = app.new_form(1, 'Register Person', lang='en')
        register_person_form.unique_id = 'register_person_form'
        register_person_form.requires = 'case'
        register_person_form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        register_person_form.actions.update_case.condition.type = 'always'
        register_person_form.actions.subcases.append(OpenSubCaseAction(
            case_type='person',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        person_module = app.add_module(Module.new_module('Manage person', None))
        person_module.unique_id = 'manage_person'
        person_module.case_type = 'person'

        person_module.case_list_form.form_id = register_person_form.unique_id

        person_module.parent_select.active = True
        person_module.parent_select.module_id = register_house_module.unique_id
        update_person_form = app.new_form(2, 'Update person', lang='en')
        update_person_form.unique_id = 'update_person_form'
        update_person_form.requires = 'case'
        update_person_form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        update_person_form.actions.update_case.condition.type = 'always'

        self.assertXmlEqual(self.get_xml('case-list-form-suite-parent-child-basic'), app.create_suite())


class CaseListFormFormTests(SimpleTestCase, TestFileMixin):
    file_path = 'data', 'case_list_form'

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def _add_module_and_form(self, ModuleClass):
        self.module = self.app.add_module(ModuleClass.new_module('New Module', lang='en'))
        self.module.case_type = 'test_case_type'
        self.form = self.module.new_form("Untitled Form", "en", self.get_xml('original_form', override_path=('data',)))

    def test_case_list_form_basic(self):
        self._add_module_and_form(Module)

        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        self.module.case_list_form.form_id = self.form.get_unique_id()

        self.assertXmlEqual(self.get_xml('case_list_form_basic_form'), self.form.render_xform())

    def test_case_list_form_advanced(self):
        self._add_module_and_form(AdvancedModule)

        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_path="/data/question1"
        ))
        self.form.actions.open_cases[0].open_condition.type = 'always'
        self.module.case_list_form.form_id = self.form.get_unique_id()

        self.assertXmlEqual(self.get_xml('case_list_form_advanced_form'), self.form.render_xform())
