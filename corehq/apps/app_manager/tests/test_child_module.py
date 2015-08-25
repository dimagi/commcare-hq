from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import FormActionCondition, OpenSubCaseAction, UpdateCaseAction, ParentSelect, \
    PreloadAction, Module, LoadUpdateAction, AdvancedModule, Application, CaseIndex
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.feature_previews import MODULE_FILTER
from corehq.toggles import NAMESPACE_DOMAIN
from toggle.shortcuts import clear_toggle_cache, update_toggle_cache


class ModuleAsChildTestBase(TestFileMixin):
    file_path = ('data', 'suite')
    child_module_class = None

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        update_toggle_cache(MODULE_FILTER.slug, self.app.domain, True, NAMESPACE_DOMAIN)
        self.module_0 = self.app.add_module(Module.new_module('parent', None))
        self.module_0.unique_id = 'm0'
        self.module_1 = self.app.add_module(self.child_module_class.new_module("child", None))
        self.module_1.unique_id = 'm1'

        for m_id in range(2):
            self.app.new_form(m_id, "Form", None)

    def tearDown(self):
        clear_toggle_cache(MODULE_FILTER.slug, self.app.domain, NAMESPACE_DOMAIN)

    def _load_case(self, child_module_form, case_type, parent_module=None):
        raise NotImplementedError()

    def test_basic_workflow(self):
        # make module_1 as submenu to module_0
        self.module_1.root_module_id = self.module_0.unique_id
        XML = """
        <partial>
          <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0"/>
          </menu>
          <menu root="m0" id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu")

    def test_workflow_with_put_in_root(self):
        # make module_1 as submenu to module_0
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_1.put_in_root = True

        XML = """
        <partial>
          <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0"/>
          </menu>
          <menu id="m0">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu")

    def test_child_module_session_datums_added(self):
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        m0f0.requires = 'case'
        m0f0.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        m0f0.actions.update_case.condition.type = 'always'
        m0f0.actions.subcases.append(OpenSubCaseAction(
            case_type='guppy',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.module_1.case_type = 'guppy'
        m1f0 = self.module_1.get_form(0)
        self._load_case(m1f0, 'gold-fish')
        self._load_case(m1f0, 'guppy', parent_module=self.module_0)

        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums-added'), self.app.create_suite(), "./entry")

    def test_deleted_parent(self):
        self.module_1.root_module_id = "unknownmodule"

        cycle_error = {
            'type': 'unknown root',
        }
        errors = self.app.validate_app()
        self.assertIn(cycle_error, errors)

    def test_circular_relation(self):
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_0.root_module_id = self.module_1.unique_id
        cycle_error = {
            'type': 'root cycle',
        }
        errors = self.app.validate_app()
        self.assertIn(cycle_error, errors)


class AdvancedModuleAsChildTest(ModuleAsChildTestBase, SimpleTestCase):
    child_module_class = AdvancedModule

    def _load_case(self, child_module_form, case_type, parent_module=None):
        action = LoadUpdateAction(case_tag=case_type, case_type=case_type)
        if parent_module:
            action.case_index = CaseIndex(tag=parent_module.case_type)

        child_module_form.actions.load_update_cases.append(action)

    def test_child_module_adjust_session_datums(self):
        """
        Test that session datum id's in child module match those in parent module
        """
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        m0f0.requires = 'case'
        m0f0.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        m0f0.actions.update_case.condition.type = 'always'

        self.module_1.case_type = 'guppy'
        m1f0 = self.module_1.get_form(0)
        self._load_case(m1f0, 'gold-fish')
        self._load_case(m1f0, 'guppy')
        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums'), self.app.create_suite(), "./entry")


class BasicModuleAsChildTest(ModuleAsChildTestBase, SimpleTestCase):
    child_module_class = Module

    def _load_case(self, child_module_form, case_type, parent_module=None):
        child_module_form.requires = 'case'
        child_module_form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        child_module_form.actions.update_case.condition.type = 'always'

        if parent_module:
            module = child_module_form.get_module()
            module.parent_select.active = True
            module.parent_select.module_id = parent_module.unique_id

    def test_grandparent_as_child_module(self):
        """
        Module 0 case_type = gold-fish
        Module 1 case_type = guppy (child of gold-fish)
        Module 2 case_type = tadpole (child of guppy, grandchild of gold-fish)

        Module 2's parent module = Module 1
        """
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        self._load_case(m0f0, 'gold-fish')
        m0f0.actions.subcases.append(OpenSubCaseAction(
            case_type='guppy',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.module_1.case_type = 'guppy'
        m1f0 = self.module_1.get_form(0)
        self._load_case(m1f0, 'guppy', parent_module=self.module_0)
        m1f0.actions.subcases.append(OpenSubCaseAction(
            case_type='tadpole',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.module_2 = self.app.add_module(self.child_module_class.new_module("grandchild", None))
        self.module_2.unique_id = 'm2'
        self.app.new_form(2, 'grandchild form', None)

        self.module_2.case_type = 'tadpole'
        m2f0 = self.module_2.get_form(0)
        self._load_case(m2f0, 'tadpole', parent_module=self.module_1)

        self.module_2.root_module_id = self.module_1.unique_id

        self.assertXmlPartialEqual(
            self.get_xml('child-module-grandchild-case'),
            self.app.create_suite(),
            "./entry"
        )

    def test_child_module_with_parent_select_entry_datums(self):
        """
            m0 - opens 'gold-fish' case.
            m1 - has m0 as root-module, has parent-select, updates 'guppy' case, creates
                 'pregnancy' subcases to guppy
        """
        self.module_1.root_module_id = self.module_0.unique_id

        # m0f0 registers gold-fish case
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        m0f0.requires = 'case'
        m0f0.actions.update_case = UpdateCaseAction(update={'question2': '/data/question2'})
        m0f0.actions.update_case.condition.type = 'always'

        # m1f0 has parent-select, updates `guppy` case, and opens sub-subcase 'pregnancy'
        self.module_1.case_type = 'guppy'
        self.module_1.parent_select = ParentSelect(
            active=True, module_id=self.module_0.unique_id
        )
        m1f0 = self.module_1.get_form(0)
        m1f0.requires = 'case'
        m1f0.actions.update_case = UpdateCaseAction(update={'question2': '/data/question2'})
        m1f0.actions.update_case.condition.type = 'always'
        m1f0.actions.subcases.append(OpenSubCaseAction(
            case_type='pregnancy',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))
        self.assertXmlPartialEqual(
            self.get_xml('child-module-with-parent-select-entry-datums-added'),
            self.app.create_suite(),
            "./entry"
        )


class UserCaseOnlyModuleAsChildTest(BasicModuleAsChildTest):
    """
    Even though a module might be usercase-only, if it acts as a parent module
    then the user should still be prompted for a case of the parent module's
    case type.

    The rationale is that child cases of the usercase never need to be
    filtered by a parent module, because they can't be filtered any more than
    they already are; there is only one usercase.
    """

    def setUp(self):
        super(UserCaseOnlyModuleAsChildTest, self).setUp()

    def test_child_module_session_datums_added(self):
        self.module_1.root_module_id = self.module_0.unique_id
        self.module_0.case_type = 'gold-fish'
        m0f0 = self.module_0.get_form(0)
        # m0 is a user-case-only module. m0f0 does not update a normal case, only the user case.
        m0f0.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'question1'})
        m0f0.actions.usercase_preload.condition.type = 'always'

        m0f0.actions.subcases.append(OpenSubCaseAction(
            case_type='guppy',
            case_name="/data/question1",
            condition=FormActionCondition(type='always')
        ))

        self.module_1.case_type = 'guppy'
        m1f0 = self.module_1.get_form(0)
        self._load_case(m1f0, 'gold-fish')
        self._load_case(m1f0, 'guppy', parent_module=self.module_0)

        self.assertXmlPartialEqual(
            self.get_xml('child-module-entry-datums-added-usercase'),
            self.app.create_suite(),
            "./entry"
        )
