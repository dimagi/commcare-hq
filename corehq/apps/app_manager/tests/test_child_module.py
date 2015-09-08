from corehq.apps.app_manager.tests import AppFactory
from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    CaseIndex,
    FormActionCondition,
    LoadUpdateAction,
    Module,
    OpenSubCaseAction,
    ParentSelect,
    PreloadAction,
    UpdateCaseAction,
)
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.feature_previews import MODULE_FILTER
from corehq.toggles import NAMESPACE_DOMAIN
from toggle.shortcuts import clear_toggle_cache, update_toggle_cache

DOMAIN = 'domain'


class ModuleAsChildTestBase(TestFileMixin):
    file_path = ('data', 'suite')
    child_module_class = None

    def setUp(self):
        update_toggle_cache(MODULE_FILTER.slug, DOMAIN, True, NAMESPACE_DOMAIN)
        self.factory = AppFactory(domain=DOMAIN)
        self.module_0, _ = self.factory.new_basic_module('parent', 'gold-fish')
        self.module_1, _ = self.factory.new_module(self.child_module_class, 'child', 'guppy', parent_module=self.module_0)

        self.app = self.factory.app

    def tearDown(self):
        clear_toggle_cache(MODULE_FILTER.slug, DOMAIN, NAMESPACE_DOMAIN)

    def test_basic_workflow(self):
        # make module_1 as submenu to module_0
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

    def test_deleted_parent(self):
        self.module_1.root_module_id = "unknownmodule"

        cycle_error = {
            'type': 'unknown root',
        }
        errors = self.app.validate_app()
        self.assertIn(cycle_error, errors)

    def test_circular_relation(self):
        self.module_0.root_module_id = self.module_1.unique_id
        cycle_error = {
            'type': 'root cycle',
        }
        errors = self.app.validate_app()
        self.assertIn(cycle_error, errors)


class AdvancedModuleAsChildTest(ModuleAsChildTestBase, SimpleTestCase):
    child_module_class = AdvancedModule

    def test_child_module_session_datums_added(self):
        m0f0 = self.module_0.get_form(0)
        self.factory.form_updates_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_updates_case(m1f0, 'gold-fish')
        self.factory.form_updates_case(m1f0, 'guppy', parent_case_type='gold-fish')

        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums-added-advanced'), self.app.create_suite(), "./entry")

    def test_child_module_adjust_session_datums(self):
        """
        Test that session datum id's in child module match those in parent module
        """
        m0f0 = self.module_0.get_form(0)
        self.factory.form_updates_case(m0f0)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_updates_case(m1f0, 'gold-fish')
        self.factory.form_updates_case(m1f0, 'guppy')
        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums'), self.app.create_suite(), "./entry")

    def test_form_case_id(self):
        """
        case_id should be renamed in an advanced submodule form
        """
        m0f0 = self.module_0.get_form(0)
        self.factory.form_updates_case(m0f0)

        m1f0 = self.module_1.get_form(0)
        m1f0.source = self.get_xml('original_form', override_path=('data',))
        self.factory.form_updates_case(m1f0, 'gold-fish', update={'question1': '/data/question1'})
        self.factory.form_updates_case(m1f0, 'guppy', parent_case_type='gold-fish')

        self.assertXmlEqual(self.get_xml('advanced_submodule_xform'), m1f0.render_xform())

    def test_form_display_condition(self):
        """
        case_id should be renamed in a basic submodule form
        """
        factory = AppFactory(domain=DOMAIN)
        m0, m0f0 = factory.new_advanced_module('parent', 'gold-fish')
        factory.form_updates_case(m0f0)

        # changing this case tag should result in the session var in the submodule entry being updated to match it
        m0f0.actions.load_update_cases[0].case_tag = 'load_goldfish_renamed'

        m1, m1f0 = factory.new_advanced_module('child', 'guppy', parent_module=m0)
        factory.form_updates_case(m1f0, 'gold-fish', update={'question1': '/data/question1'})
        factory.form_updates_case(m1f0, 'guppy', parent_case_type='gold-fish')

        # making this case tag the same as the one in the parent module should mean that it will also get changed
        # to avoid conflicts
        m1f0.actions.load_update_cases[1].case_tag = 'load_goldfish_renamed'

        m1f0.form_filter = "#case/age > 33"

        XML = """
        <partial>
          <menu id="m1" root="m0">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0" relevant="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_load_goldfish_renamed_guppy]/age &gt; 33"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(XML, factory.app.create_suite(), "./menu[@id='m1']")


class BasicModuleAsChildTest(ModuleAsChildTestBase, SimpleTestCase):
    child_module_class = Module

    def test_child_module_session_datums_added(self):
        m0f0 = self.module_0.get_form(0)
        self.factory.form_updates_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_updates_case(m1f0, 'gold-fish')
        self.factory.form_updates_case(m1f0, 'guppy', parent_case_type='gold-fish')

        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums-added-basic'), self.app.create_suite(), "./entry")

    def test_grandparent_as_child_module(self):
        """
        Module 0 case_type = gold-fish
        Module 1 case_type = guppy (child of gold-fish)
        Module 2 case_type = tadpole (child of guppy, grandchild of gold-fish)

        Module 2's parent module = Module 1
        """
        m0f0 = self.module_0.get_form(0)
        self.factory.form_updates_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_updates_case(m1f0, parent_case_type='gold-fish')
        self.factory.form_opens_case(m1f0, 'tadpole', is_subcase=True)

        m2, m2f0 = self.factory.new_basic_module('grandchild', 'tadpole')
        self.factory.form_updates_case(m2f0, parent_case_type='guppy')

        self.module_1.root_module_id = None
        m2.root_module_id = self.module_1.unique_id

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
        # m0f0 registers gold-fish case
        m0f0 = self.module_0.get_form(0)
        self.factory.form_updates_case(m0f0)

        # m1f0 has parent-select, updates `guppy` case, and opens sub-subcase 'pregnancy'
        m1f0 = self.module_1.get_form(0)
        self.factory.form_updates_case(m1f0, parent_case_type='gold-fish')
        self.factory.form_opens_case(m1f0, 'pregnancy', is_subcase=True)
        self.assertXmlPartialEqual(
            self.get_xml('child-module-with-parent-select-entry-datums-added'),
            self.app.create_suite(),
            "./entry"
        )

    def test_form_case_id(self):
        """
        case_id should be renamed in a basic submodule form
        """

        m0f0 = self.module_0.get_form(0)
        self.factory.form_updates_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        m1f0.source = self.get_xml('original_form', override_path=('data',))
        self.factory.form_updates_case(m1f0, 'guppy', parent_case_type='gold-fish', update={
            'question1': '/data/question1',
            'parent/question1': '/data/question1',
        })

        self.assertXmlEqual(self.get_xml('basic_submodule_xform'), m1f0.render_xform())

    def test_form_display_condition(self):
        """
        case_id should be renamed in a basic submodule form
        """
        m0f0 = self.module_0.get_form(0)
        self.factory.form_updates_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_updates_case(m1f0, 'guppy', parent_case_type='gold-fish', update={
            'question1': '/data/question1',
            'parent/question1': '/data/question1',
        })

        m1f0.form_filter = "#case/age > 33"

        XML = """
        <partial>
          <menu id="m1" root="m0">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0" relevant="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_guppy]/age &gt; 33"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu[@id='m1']")


class UserCaseOnlyModuleAsChildTest(ModuleAsChildTestBase, SimpleTestCase):
    """
    Even though a module might be usercase-only, if it acts as a parent module
    then the user should still be prompted for a case of the parent module's
    case type.

    The rationale is that child cases of the usercase never need to be
    filtered by a parent module, because they can't be filtered any more than
    they already are; there is only one usercase.
    """
    child_module_class = Module

    def test_child_module_session_datums_added(self):
        m0f0 = self.module_0.get_form(0)
        # m0 is a user-case-only module. m0f0 does not update a normal case, only the user case.
        m0f0.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'question1'})
        m0f0.actions.usercase_preload.condition.type = 'always'

        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_updates_case(m1f0, 'guppy', parent_case_type='gold-fish')

        self.assertXmlPartialEqual(
            self.get_xml('child-module-entry-datums-added-usercase'),
            self.app.create_suite(),
            "./entry"
        )


class AdvancedSubModuleTests(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    def test_form_rename_session_vars(self):
        """
        The session vars in the entries for the submodule should match the parent and avoid naming conflicts.
        """
        factory = AppFactory(build_version='2.9')
        reg_goldfish_mod, reg_goldfish_form = factory.new_basic_module('reg_goldfish', 'gold-fish')
        factory.form_opens_case(reg_goldfish_form)
        reg_guppy_mod, reg_guppy_form = factory.new_advanced_module('reg_guppy', 'guppy')
        factory.form_updates_case(reg_guppy_form, 'gold-fish')
        factory.form_opens_case(reg_guppy_form, 'guppy', is_subcase=True)
        upd_goldfish_mod, upd_goldfish_form = factory.new_advanced_module(
            'upd_goldfish',
            'gold-fish',
        )
        factory.form_updates_case(upd_goldfish_form)
        # changing this case tag should result in the session var in the submodule entry being updated to match it
        upd_goldfish_form.actions.load_update_cases[0].case_tag = 'load_goldfish_renamed'

        upd_guppy_mod, upd_guppy_form = factory.new_advanced_module(
            'upd_guppy',
            'guppy',
            parent_module=upd_goldfish_mod,
        )
        upd_guppy_form.source = self.get_xml('original_form', override_path=('data',))
        factory.form_updates_case(upd_guppy_form, 'gold-fish', update={'question1': '/data/question1'})
        factory.form_updates_case(
            upd_guppy_form,
            'guppy',
            parent_case_type='gold-fish',
            update={'question1': '/data/question1'}
        )
        # making this case tag the same as the one in the parent module should mean that it will also get changed
        # to avoid conflicts
        upd_guppy_form.actions.load_update_cases[1].case_tag = 'load_goldfish_renamed'

        self.assertXmlEqual(self.get_xml('child-module-rename-session-vars'), upd_guppy_form.render_xform())


class BasicSubModuleTests(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    def test_parent_preload(self):
        """
        Test parent case is correctly set in preloads when first form of parent module updates a case
        """
        factory = AppFactory(build_version='2.9')
        upd_goldfish_mod, upd_goldfish_form = factory.new_basic_module('upd_goldfish', 'gold-fish')
        factory.form_updates_case(upd_goldfish_form)

        guppy_mod, guppy_form = factory.new_basic_module(
            'upd_guppy',
            'guppy',
            parent_module=upd_goldfish_mod,
        )
        guppy_form.source = self.get_xml('original_form', override_path=('data',))
        factory.form_preloads_case(
            guppy_form,
            'guppy',
            parent_case_type='gold-fish',
            preload={'/data/question1': 'parent/question1'})

        self.assertXmlEqual(self.get_xml('child-module-preload-parent-ref'), guppy_form.render_xform())
