from django.test import SimpleTestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin, patch_get_xform_resource_overrides


@patch_get_xform_resource_overrides()
class ShadowModuleFormSelectionSuiteTest(SimpleTestCase, TestXmlMixin):

    def setUp(self):
        self.factory = AppFactory()
        self.basic_module, self.form0 = self.factory.new_basic_module('basic_module', 'parrot')
        self.form0.xmlns = 'http://openrosa.org/formdesigner/firstform'
        self.form1 = self.factory.new_form(self.basic_module)
        self.form1.xmlns = 'http://openrosa.org/formdesigner/secondform'
        self.shadow_module = self.factory.new_shadow_module('shadow_module', self.basic_module, with_form=False)
        self.child_module, self.form2 = self.factory.new_basic_module('child_module', 'parrot',
                                                                      parent_module=self.basic_module)

    def test_all_forms_selected(self, *args):
        expected = """
        <partial>
          <menu id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0"/>
            <command id="m1-f1"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected,
            self.factory.app.create_suite(),
            "./menu[@id='m1']"
        )

    def test_some_forms_selected(self, *args):
        self.shadow_module.excluded_form_ids = [self.form0.unique_id]
        expected = """
        <partial>
          <menu id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f1"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected,
            self.factory.app.create_suite(),
            "./menu[@id='m1']"
        )

    def test_no_forms_selected(self, *args):
        self.shadow_module.excluded_form_ids = [self.form0.unique_id, self.form1.unique_id]
        self.assertXmlDoesNotHaveXpath(self.factory.app.create_suite(), "./menu[@id='m1']")

    def test_no_child_forms_selected(self, *args):
        self.shadow_module.excluded_form_ids = [self.form2.unique_id]
        self.assertXmlPartialEqual(
            '''
                <partial>
                  <menu id="m0">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                    <command id="m0-f1"/>
                  </menu>
                  <menu id="m1">
                    <text>
                      <locale id="modules.m1"/>
                    </text>
                    <command id="m1-f0"/>
                    <command id="m1-f1"/>
                  </menu>
                  <menu id="m2" root="m0">
                    <text>
                      <locale id="modules.m2"/>
                    </text>
                    <command id="m2-f0"/>
                  </menu>
                </partial>
            ''',
            self.factory.app.create_suite(),
            "./menu"
        )

        self.basic_module.put_in_root = True
        self.shadow_module.put_in_root = False
        self.child_module.put_in_root = False
        self.assertXmlPartialEqual(
            '''
                <partial>
                  <menu id="root">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                    <command id="m0-f1"/>
                  </menu>
                  <menu id="m1">
                    <text>
                      <locale id="modules.m1"/>
                    </text>
                    <command id="m1-f0"/>
                    <command id="m1-f1"/>
                  </menu>
                  <menu id="m2" root="root">
                    <text>
                      <locale id="modules.m2"/>
                    </text>
                    <command id="m2-f0"/>
                  </menu>
                </partial>
            ''',
            self.factory.app.create_suite(),
            "./menu"
        )

        self.basic_module.put_in_root = False
        self.shadow_module.put_in_root = True
        self.child_module.put_in_root = False
        self.assertXmlPartialEqual(
            '''
                <partial>
                  <menu id="m0">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                    <command id="m0-f1"/>
                  </menu>
                  <menu id="root">
                    <text>
                      <locale id="modules.m1"/>
                    </text>
                    <command id="m1-f0"/>
                    <command id="m1-f1"/>
                  </menu>
                  <menu id="m2" root="m0">
                    <text>
                      <locale id="modules.m2"/>
                    </text>
                    <command id="m2-f0"/>
                  </menu>
                </partial>
            ''',
            self.factory.app.create_suite(),
            "./menu"
        )

        self.basic_module.put_in_root = False
        self.shadow_module.put_in_root = False
        self.child_module.put_in_root = True
        self.assertXmlPartialEqual(
            '''
                <partial>
                  <menu id="m0">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                    <command id="m0-f1"/>
                  </menu>
                  <menu id="m1">
                    <text>
                      <locale id="modules.m1"/>
                    </text>
                    <command id="m1-f0"/>
                    <command id="m1-f1"/>
                  </menu>
                  <menu id="m0">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m2-f0"/>
                  </menu>
                </partial>
            ''',
            self.factory.app.create_suite(),
            "./menu"
        )

        self.basic_module.put_in_root = False
        self.shadow_module.put_in_root = True
        self.child_module.put_in_root = True
        self.assertXmlPartialEqual(
            '''
                <partial>
                  <menu id="m0">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                    <command id="m0-f1"/>
                  </menu>
                  <menu id="root">
                    <text>
                      <locale id="modules.m1"/>
                    </text>
                    <command id="m1-f0"/>
                    <command id="m1-f1"/>
                  </menu>
                  <menu id="m0">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m2-f0"/>
                  </menu>
                </partial>
            ''',
            self.factory.app.create_suite(),
            "./menu"
        )

        self.basic_module.put_in_root = True
        self.shadow_module.put_in_root = False
        self.child_module.put_in_root = True
        self.assertXmlPartialEqual(
            '''
                <partial>
                  <menu id="root">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                    <command id="m0-f1"/>
                  </menu>
                  <menu id="m1">
                    <text>
                      <locale id="modules.m1"/>
                    </text>
                    <command id="m1-f0"/>
                    <command id="m1-f1"/>
                  </menu>
                  <menu id="root">
                    <text>
                      <locale id="modules.m2"/>
                    </text>
                    <command id="m2-f0"/>
                  </menu>
                </partial>
            ''',
            self.factory.app.create_suite(),
            "./menu"
        )

        self.basic_module.put_in_root = True
        self.shadow_module.put_in_root = True
        self.child_module.put_in_root = False
        self.assertXmlPartialEqual(
            '''
                <partial>
                  <menu id="root">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                    <command id="m0-f1"/>
                  </menu>
                  <menu id="root">
                    <text>
                      <locale id="modules.m1"/>
                    </text>
                    <command id="m1-f0"/>
                    <command id="m1-f1"/>
                  </menu>
                  <menu id="m2" root="root">
                    <text>
                      <locale id="modules.m2"/>
                    </text>
                    <command id="m2-f0"/>
                  </menu>
                </partial>
            ''',
            self.factory.app.create_suite(),
            "./menu"
        )

        self.basic_module.put_in_root = True
        self.shadow_module.put_in_root = True
        self.child_module.put_in_root = True
        self.assertXmlPartialEqual(
            '''
                <partial>
                  <menu id="root">
                    <text>
                      <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                    <command id="m0-f1"/>
                  </menu>
                  <menu id="root">
                    <text>
                      <locale id="modules.m1"/>
                    </text>
                    <command id="m1-f0"/>
                    <command id="m1-f1"/>
                  </menu>
                  <menu id="root">
                    <text>
                      <locale id="modules.m2"/>
                    </text>
                    <command id="m2-f0"/>
                  </menu>
                </partial>
            ''',
            self.factory.app.create_suite(),
            "./menu"
        )

    def test_form_added(self, *args):
        self.shadow_module.excluded_form_ids = [self.form0.unique_id]
        self.factory.new_form(self.basic_module)
        expected = """
        <partial>
          <menu id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f1"/>
            <command id="m1-f2"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected,
            self.factory.app.create_suite(),
            "./menu[@id='m1']"
        )

    def test_form_removed(self, *args):
        self.basic_module.forms.remove(self.form1)
        expected = """
        <partial>
          <menu id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected,
            self.factory.app.create_suite(),
            "./menu[@id='m1']"
        )

    def test_forms_reordered(self, *args):
        expected_before = """
        <partial>
          <form>http://openrosa.org/formdesigner/firstform</form>
          <form>http://openrosa.org/formdesigner/secondform</form>

          <form>http://openrosa.org/formdesigner/firstform</form>
          <form>http://openrosa.org/formdesigner/secondform</form>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected_before,
            self.factory.app.create_suite(),
            "./entry/form"
        )
        # Swap forms around
        self.basic_module.forms = [self.form1, self.form0]
        expected_after = """
        <partial>
          <form>http://openrosa.org/formdesigner/secondform</form>
          <form>http://openrosa.org/formdesigner/firstform</form>

          <form>http://openrosa.org/formdesigner/secondform</form>
          <form>http://openrosa.org/formdesigner/firstform</form>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected_after,
            self.factory.app.create_suite(),
            "./entry/form"
        )

    def _create_parent_selection_app(self):
        '''
           setUp creates an app with three modules: basic, shadow, and child, all using parrot cases.
           This app adds an additional module that uses child cases (baby_parrot) and uses it as the
           source for the shadow module. Tests verify that when the shadow module uses parent child
           selection, it fetches both parrot and baby_parrot datums, using the correct details.
        '''
        self.factory.form_requires_case(self.form0)
        self.child_case_module, self.form3 = self.factory.new_basic_module('child_case_module', 'baby_parrot')
        self.factory.form_requires_case(self.form3, parent_case_type='parrot')
        self.shadow_module.source_module_id = self.child_case_module.unique_id
        self.shadow_module.parent_select.active = True

    def test_parent_selection_first(self, *args):
        self._create_parent_selection_app()
        self.shadow_module.parent_select.module_id = self.basic_module.unique_id

        # Test the entry for the shadow module's single form
        expected_entry = """
            <partial>
              <entry>
                <command id="m1-f0">
                  <text>
                    <locale id="forms.m3f0"/>
                  </text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <instance id="commcaresession" src="jr://instance/session"/>
                <session>
                  <datum id="parent_id" nodeset="instance('casedb')/casedb/case[@case_type='parrot'][@status='open']"
                         value="./@case_id" detail-select="m0_case_short"/>
                  <datum id="case_id" nodeset="instance('casedb')/casedb/case[@case_type='baby_parrot'][@status='open'][index/parent=instance('commcaresession')/session/data/parent_id]"
                         value="./@case_id" detail-select="m1_case_short" detail-confirm="m1_case_long"/>
                </session>
              </entry>
            </partial>
        """
        self.assertXmlPartialEqual(
            expected_entry,
            self.factory.app.create_suite(),
            './entry[3]'
        )

    def test_parent_selection_different_module_than_source(self, *args):
        self._create_parent_selection_app()
        self.additional_basic_module, dummy = self.factory.new_basic_module('additional_basic_module', 'parrot')
        self.child_case_module.parent_select.active = True
        self.child_case_module.parent_select.module_id = self.basic_module.unique_id
        self.shadow_module.parent_select.module_id = self.additional_basic_module.unique_id

        # Test the entry for the shadow module's single form
        expected_entry = """
            <partial>
              <entry>
                <command id="m1-f0">
                  <text>
                    <locale id="forms.m3f0"/>
                  </text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <instance id="commcaresession" src="jr://instance/session"/>
                <session>
                  <datum id="parent_id" nodeset="instance('casedb')/casedb/case[@case_type='parrot'][@status='open']"
                         value="./@case_id" detail-select="m4_case_short"/>
                  <datum id="case_id" nodeset="instance('casedb')/casedb/case[@case_type='baby_parrot'][@status='open'][index/parent=instance('commcaresession')/session/data/parent_id]"
                         value="./@case_id" detail-select="m1_case_short" detail-confirm="m1_case_long"/>
                </session>
              </entry>
            </partial>
        """
        self.assertXmlPartialEqual(
            expected_entry,
            self.factory.app.create_suite(),
            './entry[3]'
        )

    def test_shadow_module_source_has_child_module(self, *args):
        self.factory = AppFactory()

        # m0
        self.basic_module, self.form0 = self.factory.new_basic_module('basic_module', 'parrot')
        self.form0.xmlns = 'http://openrosa.org/formdesigner/m0f0'
        self.form1 = self.factory.new_form(self.basic_module)
        self.form1.xmlns = 'http://openrosa.org/formdesigner/m0f1'

        # m1
        self.child_module, self.form2 = self.factory.new_basic_module(
            'child_module', 'parrot', parent_module=self.basic_module
        )
        self.form2.xmlns = 'http://openrosa.org/formdesigner/m1f0'
        self.child_module.put_in_root = True

        # m2
        self.shadow_module = self.factory.new_shadow_module(
            'shadow_module', self.basic_module, with_form=False
        )
        self.shadow_child_module = self.factory.new_shadow_module(
            'shadow_child', self.child_module, with_form=False
        )
        self.shadow_child_module.root_module_id = self.shadow_module.unique_id
        self.shadow_child_module.put_in_root = True

        expected_menu = ("""
        <partial>
          <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0"/>
            <command id="m0-f1"/>
          </menu>
        """                     # basic module
        """
          <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m1-f0"/>
          </menu>
        """                     # child module, put in root
        """
          <menu id="m2">
            <text>
              <locale id="modules.m2"/>
            </text>
            <command id="m2-f0"/>
            <command id="m2-f1"/>
          </menu>
        """                     # shadow module - basic
        """
          <menu id="m2">
            <text>
              <locale id="modules.m2"/>
            </text>
            <command id="m3-f0"/>
          </menu>
        """                     # shadow module - child
        """
        </partial>
        """)
        suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            expected_menu,
            suite,
            './menu',
        )

        expected_entries = ("""
            <partial>
              <entry>
                <form>http://openrosa.org/formdesigner/m0f0</form>
                <command id="m0-f0">
                  <text>
                    <locale id="forms.m0f0"/>
                  </text>
                </command>
              </entry>
        """                     # basic module, first form
        """
              <entry>
                <form>http://openrosa.org/formdesigner/m0f1</form>
                <command id="m0-f1">
                  <text>
                    <locale id="forms.m0f1"/>
                  </text>
                </command>
              </entry>
        """                     # basic module, second form
        """
              <entry>
                <form>http://openrosa.org/formdesigner/m1f0</form>
                <command id="m1-f0">
                  <text>
                    <locale id="forms.m1f0"/>
                  </text>
                </command>
              </entry>
        """                     # child module, first form
        """
              <entry>
                <form>http://openrosa.org/formdesigner/m0f0</form>
                <command id="m2-f0">
                  <text>
                    <locale id="forms.m0f0"/>
                  </text>
                </command>
              </entry>
        """                     # shadow basic module, first form
        """
              <entry>
                <form>http://openrosa.org/formdesigner/m0f1</form>
                <command id="m2-f1">
                  <text>
                    <locale id="forms.m0f1"/>
                  </text>
                </command>
              </entry>
        """                     # shadow basic module, second form
        """
              <entry>
                <form>http://openrosa.org/formdesigner/m1f0</form>
                <command id="m3-f0">
                  <text>
                    <locale id="forms.m1f0"/>
                  </text>
                </command>
              </entry>
        """                     # shadow child module, first form
        """
            </partial>
        """)
        self.assertXmlPartialEqual(
            expected_entries,
            suite,
            './entry',
        )
