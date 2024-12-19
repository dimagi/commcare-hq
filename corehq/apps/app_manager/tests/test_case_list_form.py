from django.test import SimpleTestCase

from unittest.mock import patch

from corehq.apps.app_manager.const import (
    AUTO_SELECT_USERCASE,
    WORKFLOW_CASE_LIST,
    WORKFLOW_MODULE,
)
from corehq.apps.app_manager.models import (
    AdvancedModule,
    AdvancedOpenCaseAction,
    Application,
    AutoSelectCase,
    ConditionalCaseUpdate,
    DetailColumn,
    LoadUpdateAction,
    Module,
    OpenCaseAction,
    PreloadAction,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import patch_get_xform_resource_overrides, TestXmlMixin
from corehq.util.test_utils import flag_enabled


@patch('corehq.apps.app_manager.helpers.validators.domain_has_privilege', return_value=True)
@patch_get_xform_resource_overrides()
class CaseListFormSuiteTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'case_list_form')

    def _prep_case_list_form_app(self):
        return AppFactory.case_list_form_app_factory()

    def test_case_list_registration_form(self, *args):
        factory = self._prep_case_list_form_app()
        app = factory.app
        case_module = app.get_module(0)
        AppFactory.add_module_case_detail_column(case_module, 'short', 'dob', 'birthday')
        case_module.case_list_form.set_icon('en', 'jr://file/commcare/image/new_case.png')
        case_module.case_list_form.set_audio('en', 'jr://file/commcare/audio/new_case.mp3')
        self.assertXmlEqual(self.get_xml('case-list-form-suite'), app.create_suite())

    def test_case_list_registration_form_usercase(self, *args):
        factory = self._prep_case_list_form_app()
        app = factory.app
        register_module = app.get_module(1)
        register_form = register_module.get_form(0)
        register_form.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'question1'})
        register_form.actions.usercase_preload.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('case-list-form-suite-usercase'), app.create_suite())

    def test_case_list_registration_form_end_for_form_nav(self, *args):
        factory = self._prep_case_list_form_app()
        app = factory.app
        registration_form = app.get_module(1).get_form(0)
        registration_form.post_form_workflow = WORKFLOW_MODULE

        self.assertXmlPartialEqual(
            self.get_xml('case-list-form-suite-form-nav-entry'),
            app.create_suite(),
            "./entry[2]"
        )

    def test_case_list_registration_form_no_media(self, *args):
        factory = self._prep_case_list_form_app()
        self.assertXmlPartialEqual(
            self.get_xml('case-list-form-suite-no-media-partial'),
            factory.app.create_suite(),
            "./detail[@id='m0_case_short']/action"
        )

    def test_case_list_form_multiple_modules(self, *args):
        factory = self._prep_case_list_form_app()
        case_module1 = factory.app.get_module(0)

        case_module2, update2 = factory.new_basic_module('update case 2', case_module1.case_type)
        factory.form_requires_case(update2)

        case_module2.case_list_form.form_id = factory.get_form(1, 0).unique_id
        case_module2.case_list_form.label = {
            'en': 'New Case'
        }

        self.assertXmlEqual(
            self.get_xml('case-list-form-suite-multiple-references'),
            factory.app.create_suite(),
        )

    def test_case_list_registration_form_advanced(self, *args):
        factory = AppFactory(build_version='2.9.0')

        register_module, register_form = factory.new_advanced_module('register_dugong', 'dugong')
        factory.form_opens_case(register_form)

        case_module, update_form = factory.new_advanced_module('update_dugong', 'dugong')
        factory.form_requires_case(update_form)

        case_module.case_list_form.form_id = register_form.get_unique_id()
        case_module.case_list_form.label = {
            'en': 'Register another Dugong'
        }
        self.assertXmlEqual(self.get_xml('case-list-form-advanced'), factory.app.create_suite())

    def test_case_list_registration_form_advanced_autoload(self, *args):
        factory = AppFactory(build_version='2.9.0')

        register_module, register_form = factory.new_advanced_module('register_dugong', 'dugong')
        factory.form_opens_case(register_form)
        register_form.actions.load_update_cases.append(LoadUpdateAction(
            case_tag='usercase',
            auto_select=AutoSelectCase(
                mode=AUTO_SELECT_USERCASE,
            )
        ))

        case_module, update_form = factory.new_advanced_module('update_dugong', 'dugong')
        factory.form_requires_case(update_form)

        case_module.case_list_form.form_id = register_form.get_unique_id()
        case_module.case_list_form.label = {
            'en': 'Register another Dugong'
        }
        self.assertXmlEqual(self.get_xml('case-list-form-advanced-autoload'), factory.app.create_suite())

    def test_case_list_registration_form_return_to_case_list(self, *args):
        factory = self._prep_case_list_form_app()
        app = factory.app
        case_module = app.get_module(0)
        case_module.case_list_form.post_form_workflow = WORKFLOW_CASE_LIST
        self.assertXmlEqual(self.get_xml('case_list_form_end_of_form_case_list'), app.create_suite())

    def test_case_list_registration_form_return_to_case_list_clmi_only(self, *args):
        factory = self._prep_case_list_form_app()
        app = factory.app
        clmi_module = factory.new_basic_module('clmi_only', factory.app.get_module(0).case_type, with_form=False)

        case_module = app.get_module(0)
        case_module.case_list_form.post_form_workflow = WORKFLOW_CASE_LIST

        clmi_module.case_list_form.form_id = case_module.case_list_form.form_id
        clmi_module.case_list_form.post_form_workflow = WORKFLOW_CASE_LIST
        clmi_module.case_list.show = True

        #self.assertXmlEqual(self.get_xml('case_list_form_end_of_form_case_list_clmi_only'), app.create_suite())
        self.assertXmlPartialEqual(self.get_xml('case_list_form_end_of_form_case_list_clmi_only'),
                                   factory.app.create_suite(), './entry[2]')

    def test_case_list_form_parent_child_advanced(self, *args):
        # * Register house (case type = house, basic)
        #   * Register house form
        # * Register person (case type = person, parent select = 'Register house', advanced)
        #   * Register person form
        # * Manager person (case type = person, case list form = 'Register person form', basic)
        #   * Manage person form
        factory = AppFactory(build_version='2.9.0')
        register_house_module, register_house_form = factory.new_basic_module('register_house', 'house')
        factory.form_opens_case(register_house_form)

        register_person_module, register_person_form = factory.new_advanced_module('register_person', 'person')
        factory.form_requires_case(register_person_form, 'house')
        factory.form_opens_case(register_person_form, 'person', is_subcase=True)

        person_module, update_person_form = factory.new_basic_module(
            'update_person',
            'person',
            case_list_form=register_person_form
        )
        person_module.parent_select.active = True
        person_module.parent_select.module_id = register_house_module.unique_id

        factory.form_requires_case(update_person_form)

        self.assertXmlEqual(self.get_xml('case-list-form-suite-parent-child-advanced'), factory.app.create_suite())

    def test_case_list_form_followup_form(self, *args):
        # * Register house (case type = house, basic)
        #   * Register house form
        # * Register person (case type = person, parent select = 'Register house', advanced)
        #   * Register person form
        # * Manager person (case type = person, case list form = 'Register person form', basic)
        #   * Manage person form
        factory = AppFactory(build_version='2.9.0')
        register_house_module, register_house_form = factory.new_basic_module('register_house', 'house')
        factory.form_opens_case(register_house_form)

        register_person_module, register_person_form = factory.new_advanced_module('register_person', 'person')
        factory.form_requires_case(register_person_form, 'house')
        factory.form_opens_case(register_person_form, 'person', is_subcase=True)

        house_module, update_house_form = factory.new_advanced_module(
            'update_house',
            'house',
        )
        factory.form_requires_case(update_house_form)

        person_module, update_person_form = factory.new_basic_module(
            'update_person',
            'person',
            case_list_form=update_house_form
        )
        factory.form_requires_case(update_person_form)

        def _assert_app_build_error(error):
            errors = factory.app.validate_app()
            self.assertIn(
                (error, person_module.unique_id),
                [(e["type"], e.get("module", {}).get("unique_id", {})) for e in errors]
            )
            self.assertXmlPartialEqual(
                "<partial></partial>",
                factory.app.create_suite(),
                "./detail[@id='m3_case_short']/action"
            )
        # should fail since feature flag isn't enabled
        _assert_app_build_error('case list form not registration')
        with flag_enabled('FOLLOWUP_FORMS_AS_CASE_LIST_FORM'):
            # should fail since module doesn't have active parent_select
            _assert_app_build_error("invalid case list followup form")

            person_module.parent_select.active = True
            person_module.parent_select.module_id = register_house_module.unique_id
            person_module.case_list_form.relevancy_expression = "count(instance('casedb')/casedb/case) != 0"
            errors = factory.app.validate_app()
            self.assertNotIn(
                ('case list form not registration', person_module.unique_id),
                [(e["type"], e.get("module", {}).get("unique_id", {})) for e in errors]
            )
            xml = """
            <partial>
            <action relevant="count(instance('casedb')/casedb/case) != 0">
                <display>
                    <text><locale id="case_list_form.m3"/></text>
                </display>
                <stack>
                <push>
                    <command value="'m2-f0'"/>
                    <datum id="case_id_load_house_0" value="instance('commcaresession')/session/data/parent_id"/>
                    <datum id="return_to" value="'m3'"/>
                </push>
                </stack>
            </action>
            </partial>
            """
            self.assertXmlPartialEqual(
                xml,
                factory.app.create_suite(),
                "./detail[@id='m3_case_short']/action"
            )
            person_module.parent_select.active = False

    def test_case_list_form_parent_child_basic(self, *args):
        # * Register house (case type = house, basic)
        #   * Register house form
        # * Register person (case type = person, parent select = 'Register house', basic)
        #   * Register person form
        # * Manager person (case type = person, case list form = 'Register person form', basic)
        #   * Manage person form
        factory = AppFactory(build_version='2.9.0')
        register_house_module, register_house_form = factory.new_basic_module('register_house', 'house')

        factory.form_opens_case(register_house_form)

        register_person_module, register_person_form = factory.new_basic_module('register_person', 'house')
        factory.form_requires_case(register_person_form)
        factory.form_opens_case(register_person_form, case_type='person', is_subcase=True)

        person_module, update_person_form = factory.new_basic_module(
            'update_person',
            'person',
            case_list_form=register_person_form
        )

        factory.form_requires_case(update_person_form, parent_case_type='house')
        register_person_module.case_details.short.columns.append(
            DetailColumn(
                header={'en': 'a'},
                model='case',
                field='parent/case_name',  # Include a parent case property in the case list
                format='plain',
            )
        )

        self.assertXmlEqual(self.get_xml('case-list-form-suite-parent-child-basic'), factory.app.create_suite())

    def test_case_list_form_reg_form_creates_child_case(self, *args):
        factory = AppFactory(build_version='2.9.0')
        register_person_module, register_person_form = factory.new_basic_module('reg_person_and_stub', 'person')

        factory.form_opens_case(register_person_form)
        factory.form_opens_case(register_person_form, case_type='stub', is_subcase=True)

        person_module, update_person_form = factory.new_basic_module(
            'update_person',
            'person',
            case_list_form=register_person_form
        )

        factory.form_requires_case(update_person_form)
        self.assertXmlPartialEqual(
            self.get_xml('case_list_form_reg_form_creates_child_case'), factory.app.create_suite(), './entry[1]'
        )

    def test_case_list_form_parent_child_submodule_basic(self, *args):
        # * Register house (case type = house, basic)
        #   * Register house form
        # * Register person (case type = person, parent select = 'Register house', basic)
        #   * Register person form
        # * Update house (case type = house, case list form = 'Register house')
        #   * Update house form
        #   * Update person (case type = person, case list form = 'Register person form', basic, parent module = 'Update house')
        #       * Update person form
        factory = AppFactory(build_version='2.9.0')
        register_house_module, register_house_form = factory.new_basic_module('register_house', 'house')
        factory.form_opens_case(register_house_form)

        register_person_module, register_person_form = factory.new_basic_module('register_person', 'house')
        factory.form_requires_case(register_person_form, 'house')
        factory.form_opens_case(register_person_form, 'person', is_subcase=True)

        house_module, update_house_form = factory.new_basic_module(
            'update_house',
            'house',
            case_list_form=register_house_form
        )
        factory.form_requires_case(update_house_form)

        person_module, update_person_form = factory.new_basic_module(
            'update_person',
            'person',
            parent_module=house_module,
            case_list_form=register_person_form
        )

        factory.form_requires_case(update_person_form, 'person', parent_case_type='house')

        self.assertXmlEqual(self.get_xml('case-list-form-suite-parent-child-submodule-basic'), factory.app.create_suite())

    def test_case_list_form_parent_child_submodule_advanced(self, *args):
        # * Register house (case type = house, basic)
        #   * Register house form
        # * Register person (case type = person, parent select = 'Register house', advanced)
        #   * Register person form
        # * Update house (case type = house, case list form = 'Register house')
        #   * Update house form
        #   * Update person (case type = person, case list form = 'Register person form', advanced, parent module = 'Update house')
        #       * Update person form
        factory = AppFactory(build_version='2.9.0')
        register_house_module, register_house_form = factory.new_basic_module('register_house', 'house')
        factory.form_opens_case(register_house_form)

        register_person_module, register_person_form = factory.new_advanced_module('register_person', 'person')
        factory.form_requires_case(register_person_form, 'house')
        factory.form_opens_case(register_person_form, 'person', is_subcase=True)

        house_module, update_house_form = factory.new_advanced_module(
            'update_house',
            'house',
            case_list_form=register_house_form
        )

        factory.form_requires_case(update_house_form)

        person_module, update_person_form = factory.new_advanced_module(
            'update_person',
            'person',
            parent_module=house_module,
            case_list_form=register_person_form
        )

        factory.form_requires_case(update_person_form, 'house')
        factory.form_requires_case(update_person_form, 'person', parent_case_type='house')

        self.assertXmlEqual(self.get_xml('case-list-form-suite-parent-child-submodule-advanced'), factory.app.create_suite())

    def test_case_list_form_parent_child_submodule_advanced_rename_case_var(self, *args):
        # Test that the session vars in the entries for the submodule get updated
        # to match the parent (and to avoid naming conflicts).
        # m3-f0: 'case_id_load_house' -> 'case_id_load_house_renamed'
        # m3-f0: 'case_id_load_house_renamed' -> 'case_id_load_house_renamed_person'
        factory = AppFactory(build_version='2.9.0')
        register_house_module, register_house_form = factory.new_basic_module('register_house', 'house')
        factory.form_opens_case(register_house_form)

        register_person_module, register_person_form = factory.new_advanced_module('register_person', 'person')
        factory.form_requires_case(register_person_form, 'house')
        factory.form_opens_case(register_person_form, 'person', is_subcase=True)

        house_module, update_house_form = factory.new_advanced_module(
            'update_house',
            'house',
            case_list_form=register_house_form
        )

        factory.form_requires_case(update_house_form)
        # changing this case tag should result in the session var in the submodule entry being updated to match it
        update_house_form.actions.load_update_cases[0].case_tag = 'load_house_renamed'

        person_module, update_person_form = factory.new_advanced_module(
            'update_person',
            'person',
            parent_module=house_module,
            case_list_form=register_person_form
        )

        factory.form_requires_case(update_person_form, 'house')
        factory.form_requires_case(update_person_form, 'person', parent_case_type='house')
        # making this case tag the same as the one in the parent module should mean that it will also
        # get changed to avoid conflicts
        update_person_form.actions.load_update_cases[1].case_tag = 'load_house_renamed'

        self.assertXmlEqual(self.get_xml('case-list-form-suite-parent-child-submodule-advanced-rename-var'), factory.app.create_suite())

    def test_case_list_form_parent_child_submodule_mixed(self, *args):
        # * Register house (case type = house, basic)
        #   * Register house form
        # * Register person (case type = person, parent select = 'Register house', advanced)
        #   * Register person form
        # * Update house (case type = house, case list form = 'Register house')
        #   * Update house form
        #   * Update person (case type = person, case list form = 'Register person form', advanced, parent module = 'Update house')
        #       * Update person form
        factory = AppFactory(build_version='2.9.0')
        register_house_module, register_house_form = factory.new_basic_module('register_house', 'house')
        factory.form_opens_case(register_house_form)

        register_person_module, register_person_form = factory.new_basic_module('register_person', 'house')
        factory.form_requires_case(register_person_form, 'house')
        factory.form_opens_case(register_person_form, 'person', is_subcase=True)

        house_module, update_house_form = factory.new_advanced_module(
            'update_house',
            'house',
            case_list_form=register_house_form
        )

        factory.form_requires_case(update_house_form)

        person_module, update_person_form = factory.new_basic_module(
            'update_person',
            'person',
            parent_module=house_module,
            case_list_form=register_person_form
        )

        factory.form_requires_case(update_person_form, 'person', parent_case_type='house')

        self.assertXmlEqual(self.get_xml('case-list-form-suite-parent-child-submodule-mixed'), factory.app.create_suite())

    def test_target_module_different_datums(self, *args):
        # * Registration
        #   * Register patient form
        #     * open case (patient), update usercase
        # * Visits (case type = patient, case list form = 'Register patient')
        #   * Visit form
        #     * update case, open child case (visit), load from usercase
        #   * Record notes
        #     * update case, open child case (visit)
        #   * Update patient
        #     * update case
        factory = AppFactory(build_version='2.9.0')
        registration_module, registration_form = factory.new_basic_module('registration', 'patient')

        factory.form_opens_case(registration_form)
        factory.form_uses_usercase(registration_form, preload={'username': '/data/username'})

        visit_module, visit_form = factory.new_basic_module(
            'visits',
            'patient',
            case_list_form=registration_form
        )

        factory.form_requires_case(visit_form)
        factory.form_opens_case(visit_form, 'visit', is_subcase=True)
        factory.form_uses_usercase(visit_form, preload={'username': '/data/username'})

        notes_form = factory.new_form(visit_module)
        factory.form_requires_case(notes_form)
        factory.form_opens_case(notes_form, 'visit', is_subcase=True)

        update_patient_form = factory.new_form(visit_module)
        factory.form_requires_case(update_patient_form)

        self.assertXmlPartialEqual(
            self.get_xml('target_module_different_datums'),
            factory.app.create_suite(),
            './entry')

    def test_case_list_form_requires_parent_case_but_target_doesnt(self, *args):
        factory = AppFactory(build_version='2.9.0')
        register_household_module, register_household_form = factory.new_basic_module('new_household', 'household')
        factory.form_opens_case(register_household_form)

        households, edit_household_form = factory.new_basic_module('households', 'household',
                                                                   case_list_form=register_household_form)
        factory.form_requires_case(edit_household_form)

        register_member_module, register_member_form = factory.new_advanced_module('new_member', 'member')
        factory.form_requires_case(register_member_form, 'household')
        factory.form_opens_case(register_member_form, 'member', is_subcase=True)

        members, edit_member_form = factory.new_basic_module('members', 'member', case_list_form=register_member_form)
        factory.form_requires_case(edit_member_form)

        suite = factory.app.create_suite()
        self.assertXmlEqual(
            self.get_xml('source_requires_case_target_doesnt'),
            suite
        )


class CaseListFormFormTests(SimpleTestCase, TestXmlMixin):
    file_path = 'data', 'case_list_form'

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_patch.start()

        self.app = Application.new_app('domain', 'New App')
        self.app.version = 3

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def _add_module_and_form(self, ModuleClass):
        self.module = self.app.add_module(ModuleClass.new_module('New Module', lang='en'))
        self.module.case_type = 'test_case_type'
        self.form = self.module.new_form("Untitled Form", "en",
                                         self.get_xml('original_form', override_path=('data',)).decode('utf-8'))

    def test_case_list_form_basic(self):
        self._add_module_and_form(Module)

        self.form.actions.open_case = OpenCaseAction(
            name_update=ConditionalCaseUpdate(question_path="/data/question1"),
            external_id=None
        )
        self.form.actions.open_case.condition.type = 'always'
        self.module.case_list_form.form_id = self.form.get_unique_id()

        self.assertXmlEqual(self.get_xml('case_list_form_basic_form'), self.form.render_xform())

    def test_case_list_form_advanced(self):
        self._add_module_and_form(AdvancedModule)

        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_update=ConditionalCaseUpdate(question_path="/data/question1"),
        ))
        self.form.actions.open_cases[0].open_condition.type = 'always'
        self.module.case_list_form.form_id = self.form.get_unique_id()

        self.assertXmlEqual(self.get_xml('case_list_form_advanced_form'), self.form.render_xform())
