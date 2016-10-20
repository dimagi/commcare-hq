from django.test import SimpleTestCase
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


class ShadowModuleFormSelectionSuiteTest(SimpleTestCase, TestXmlMixin):

    def setUp(self):
        self.factory = AppFactory()
        self.basic_module, self.form0 = self.factory.new_basic_module('basic_module', 'parrot')
        self.form0.xmlns = 'http://openrosa.org/formdesigner/firstform'
        self.form1 = self.factory.new_form(self.basic_module)
        self.form1.xmlns = 'http://openrosa.org/formdesigner/secondform'
        self.shadow_module = self.factory.new_shadow_module('shadow_module', self.basic_module, with_form=False)

    def test_all_forms_selected(self):
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

    def test_some_forms_selected(self):
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

    def test_no_forms_selected(self):
        self.shadow_module.excluded_form_ids = [self.form0.unique_id, self.form1.unique_id]
        expected = """
        <partial>
          <menu id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected,
            self.factory.app.create_suite(),
            "./menu[@id='m1']"
        )

    def test_form_added(self):
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

    def test_form_removed(self):
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

    def test_forms_reordered(self):
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
