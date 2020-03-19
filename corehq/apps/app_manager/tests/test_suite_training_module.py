from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import TestXmlMixin, patch_get_xform_resource_overrides


@patch_get_xform_resource_overrides()
class TrainingModuleSuiteTest(SimpleTestCase, TestXmlMixin):

    def test_training_module(self, *args):
        app = Application.new_app('domain', 'Untitled Application')
        training_module = app.add_module(Module.new_training_module('training module', None))
        app.new_form(training_module.id, "Untitled Form", None)
        self.assertXmlPartialEqual(
            """
            <partial>
                <menu root="training-root" id="m0">
                    <text>
                        <locale id="modules.m0"/>
                    </text>
                    <command id="m0-f0"/>
                </menu>
                <menu id="training-root">
                    <text>
                        <locale id="training.root.title"/>
                    </text>
                </menu>
            </partial>
            """,
            app.create_suite(),
            "./menu"
        )

    def test_training_module_put_in_root(self, *args):
        app = Application.new_app('domain', 'Untitled Application')
        training_module = app.add_module(Module.new_training_module('training module', None))
        training_module.put_in_root = True
        app.new_form(training_module.id, "Untitled Form", None)
        self.assertXmlPartialEqual(
            """
            <partial>
                <menu id="training-root">
                    <text>
                        <locale id="training.root.title"/>
                    </text>
                    <command id="m0-f0"/>
                </menu>
            </partial>
            """,
            app.create_suite(),
            "./menu"
        )
