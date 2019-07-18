from __future__ import absolute_import
from __future__ import unicode_literals
from mock import patch

from corehq.apps.app_manager.tests.app_factory import AppFactory
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Module,
    PreloadAction,
)
from corehq.apps.app_manager.const import WORKFLOW_PREVIOUS
from corehq.apps.app_manager.tests.util import TestXmlMixin

DOMAIN = 'domain'


class ModuleAsChildTestBase(TestXmlMixin):
    file_path = ('data', 'suite')
    child_module_class = None

    def setUp(self):
        self.factory = AppFactory(build_version='2.9.0', domain=DOMAIN)
        self.module_0, _ = self.factory.new_basic_module('parent', 'gold-fish')
        self.module_1, _ = self.factory.new_module(self.child_module_class, 'child', 'guppy', parent_module=self.module_0)

        self.app = self.factory.app

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
              <locale id="modules.m0"/>
            </text>
            <command id="m1-f0"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(XML, self.app.create_suite(), "./menu")

    @patch('corehq.apps.app_manager.helpers.validators.domain_has_privilege', return_value=True)
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    @patch('corehq.apps.builds.models.BuildSpec.supports_j2me', return_value=False)
    def test_deleted_parent(self, *args):
        self.module_1.root_module_id = "unknownmodule"

        cycle_error = {
            'type': 'unknown root',
        }
        errors = self.app.validate_app()
        self.assertIn(cycle_error, errors)

    @patch('corehq.apps.app_manager.helpers.validators.domain_has_privilege', return_value=True)
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    @patch('corehq.apps.builds.models.BuildSpec.supports_j2me', return_value=False)
    def test_circular_relation(self, *args):
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
        self.factory.form_requires_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_requires_case(m1f0, 'gold-fish')
        self.factory.form_requires_case(m1f0, 'guppy', parent_case_type='gold-fish')

        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums-added-advanced'), self.app.create_suite(), "./entry")

    def test_child_module_adjust_session_datums(self):
        """
        Test that session datum id's in child module match those in parent module
        """
        m0f0 = self.module_0.get_form(0)
        self.factory.form_requires_case(m0f0)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_requires_case(m1f0, 'gold-fish')
        self.factory.form_requires_case(m1f0, 'guppy')
        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums'), self.app.create_suite(), "./entry")

    def test_form_case_id(self):
        """
        case_id should be renamed in an advanced submodule form
        """
        m0f0 = self.module_0.get_form(0)
        self.factory.form_requires_case(m0f0)

        m1f0 = self.module_1.get_form(0)
        m1f0.source = self.get_xml('original_form', override_path=('data',)).decode('utf-8')
        self.factory.form_requires_case(m1f0, 'gold-fish', update={'question1': '/data/question1'})
        self.factory.form_requires_case(m1f0, 'guppy', parent_case_type='gold-fish')

        self.assertXmlEqual(self.get_xml('advanced_submodule_xform'), m1f0.render_xform())

    def test_form_display_condition(self):
        """
        case_id should be renamed in a basic submodule form
        """
        factory = AppFactory(domain=DOMAIN)
        m0, m0f0 = factory.new_advanced_module('parent', 'gold-fish')
        factory.form_requires_case(m0f0)

        # changing this case tag should result in the session var in the submodule entry being updated to match it
        m0f0.actions.load_update_cases[0].case_tag = 'load_goldfish_renamed'

        m1, m1f0 = factory.new_advanced_module('child', 'guppy', parent_module=m0)
        factory.form_requires_case(m1f0, 'gold-fish', update={'question1': '/data/question1'})
        factory.form_requires_case(m1f0, 'guppy', parent_case_type='gold-fish')

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
        self.factory.form_requires_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_requires_case(m1f0, 'gold-fish')
        self.factory.form_requires_case(m1f0, 'guppy', parent_case_type='gold-fish')

        self.assertXmlPartialEqual(self.get_xml('child-module-entry-datums-added-basic'), self.app.create_suite(), "./entry")

        self.factory.form_workflow(m1f0, WORKFLOW_PREVIOUS)
        self.assertXmlPartialEqual(self.get_xml('child-module-form-workflow-previous'), self.app.create_suite(), "./entry")

    def test_grandparent_as_child_module(self):
        """
        Module 0 case_type = gold-fish
        Module 1 case_type = guppy (child of gold-fish)
        Module 2 case_type = tadpole (child of guppy, grandchild of gold-fish)

        Module 2's parent module = Module 1
        """
        m0f0 = self.module_0.get_form(0)
        self.factory.form_requires_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_requires_case(m1f0, parent_case_type='gold-fish')
        self.factory.form_opens_case(m1f0, 'tadpole', is_subcase=True)

        m2, m2f0 = self.factory.new_basic_module('grandchild', 'tadpole')
        self.factory.form_requires_case(m2f0, parent_case_type='guppy')

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
        self.factory.form_requires_case(m0f0)

        # m1f0 has parent-select, updates `guppy` case, and opens sub-subcase 'pregnancy'
        m1f0 = self.module_1.get_form(0)
        self.factory.form_requires_case(m1f0, parent_case_type='gold-fish')
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
        self.factory.form_requires_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        m1f0.source = self.get_xml('original_form', override_path=('data',)).decode('utf-8')
        self.factory.form_requires_case(m1f0, 'guppy', parent_case_type='gold-fish', update={
            'question1': '/data/question1',
            'parent/question1': '/data/question1',
        })

        self.assertXmlEqual(self.get_xml('basic_submodule_xform'), m1f0.render_xform())

    def test_form_display_condition(self):
        """
        case_id should be renamed in a basic submodule form
        """
        m0f0 = self.module_0.get_form(0)
        self.factory.form_requires_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        m1f0 = self.module_1.get_form(0)
        self.factory.form_requires_case(m1f0, 'guppy', parent_case_type='gold-fish', update={
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

    def test_child_module_no_forms_show_case_list(self):
        m0f0 = self.module_0.get_form(0)
        self.factory.form_requires_case(m0f0)

        del self.module_1['forms'][0]

        self.module_1.case_list.show = True
        self.module_1.case_list.lable = {"en": "Case List"}

        self.module_1.parent_select.active = True
        self.module_1.parent_select.module_id = self.module_0.unique_id

        self.assertXmlPartialEqual(
            self.get_xml('child-module-with-parent-select-and-case-list'),
            self.app.create_suite(),
            "./entry"
        )


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
        self.factory.form_requires_case(m1f0, 'guppy', parent_case_type='gold-fish')

        self.assertXmlPartialEqual(
            self.get_xml('child-module-entry-datums-added-usercase'),
            self.app.create_suite(),
            "./entry"
        )


class AdvancedSubModuleTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def test_form_rename_session_vars(self):
        """
        The session vars in the entries for the submodule should match the parent and avoid naming conflicts.
        """
        factory = AppFactory(build_version='2.9.0')
        reg_goldfish_mod, reg_goldfish_form = factory.new_basic_module('reg_goldfish', 'gold-fish')
        factory.form_opens_case(reg_goldfish_form)
        reg_guppy_mod, reg_guppy_form = factory.new_advanced_module('reg_guppy', 'guppy')
        factory.form_requires_case(reg_guppy_form, 'gold-fish')
        factory.form_opens_case(reg_guppy_form, 'guppy', is_subcase=True)
        upd_goldfish_mod, upd_goldfish_form = factory.new_advanced_module(
            'upd_goldfish',
            'gold-fish',
        )
        factory.form_requires_case(upd_goldfish_form)
        # changing this case tag should result in the session var in the submodule entry being updated to match it
        upd_goldfish_form.actions.load_update_cases[0].case_tag = 'load_goldfish_renamed'

        upd_guppy_mod, upd_guppy_form = factory.new_advanced_module(
            'upd_guppy',
            'guppy',
            parent_module=upd_goldfish_mod,
        )
        upd_guppy_form.source = self.get_xml('original_form', override_path=('data',)).decode('utf-8')
        factory.form_requires_case(upd_guppy_form, 'gold-fish', update={'question1': '/data/question1'})
        factory.form_requires_case(
            upd_guppy_form,
            'guppy',
            parent_case_type='gold-fish',
            update={'question1': '/data/question1'}
        )
        # making this case tag the same as the one in the parent module should mean that it will also get changed
        # to avoid conflicts
        upd_guppy_form.actions.load_update_cases[1].case_tag = 'load_goldfish_renamed'

        self.assertXmlEqual(self.get_xml('child-module-rename-session-vars'), upd_guppy_form.render_xform())

    def test_incorrect_case_var_for_case_update(self):
        # see http://manage.dimagi.com/default.asp?230013
        factory = AppFactory(build_version='2.9.0')
        new_episode_module, new_episode_form = factory.new_basic_module('register_episode', 'episode')
        factory.form_opens_case(new_episode_form)

        lab_test_module, lab_test_form = factory.new_advanced_module('lab_test', 'episode')
        factory.form_requires_case(lab_test_form, 'episode')
        factory.form_opens_case(lab_test_form, 'lab_test', is_subcase=True, is_extension=True)
        factory.form_opens_case(lab_test_form, 'lab_referral', is_subcase=True, parent_tag='open_lab_test')

        lab_update_module, lab_update_form = factory.new_advanced_module('lab_update', 'lab_test', parent_module=lab_test_module)
        factory.form_requires_case(lab_update_form, 'episode', update={'episode_type': '/data/question1'})
        factory.form_requires_case(lab_update_form, 'lab_test', parent_case_type='episode')
        lab_update_form.source = self.get_xml('original_form', override_path=('data',)).decode('utf-8')

        expected_suite_entry = """
        <partial>
            <session>
                <datum id="case_id_load_episode_0" nodeset="instance('casedb')/casedb/case[@case_type='episode'][@status='open']" value="./@case_id" detail-select="m0_case_short"/>
                <datum id="case_id_new_lab_test_0" function="uuid()"/>
                <datum id="case_id_new_lab_referral_1" function="uuid()"/>
                <datum id="case_id_load_lab_test_0" nodeset="instance('casedb')/casedb/case[@case_type='lab_test'][@status='open'][index/parent=instance('commcaresession')/session/data/case_id_load_episode_0]" value="./@case_id" detail-select="m2_case_short" detail-confirm="m2_case_long"/>
            </session>
        </partial>"""
        suite_xml = factory.app.create_suite()
        self.assertXmlPartialEqual(
            expected_suite_entry,
            suite_xml,
            './entry[3]/session'
        )
        form_xml = lab_update_form.render_xform().decode('utf-8')
        self.assertTrue(
            '<bind calculate="instance(\'commcaresession\')/session/data/case_id_new_lab_test_0" nodeset="/data/case_load_episode_0/case/@case_id"/>' not in form_xml
        )
        self.assertTrue(
            '<bind calculate="instance(\'commcaresession\')/session/data/case_id_load_episode_0" nodeset="/data/case_load_episode_0/case/@case_id"/>' in form_xml
        )


class BasicSubModuleTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def test_parent_preload(self):
        """
        Test parent case is correctly set in preloads when first form of parent module updates a case
        """
        factory = AppFactory(build_version='2.9.0')
        upd_goldfish_mod, upd_goldfish_form = factory.new_basic_module('upd_goldfish', 'gold-fish')
        factory.form_requires_case(upd_goldfish_form)

        guppy_mod, guppy_form = factory.new_basic_module(
            'upd_guppy',
            'guppy',
            parent_module=upd_goldfish_mod,
        )
        guppy_form.source = self.get_xml('original_form', override_path=('data',)).decode('utf-8')
        factory.form_requires_case(
            guppy_form,
            'guppy',
            parent_case_type='gold-fish',
            preload={'/data/question1': 'parent/question1'})

        self.assertXmlEqual(self.get_xml('child-module-preload-parent-ref'), guppy_form.render_xform())
