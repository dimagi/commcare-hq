from django.test import TestCase

import jsonobject

from corehq.apps.app_manager.models import Application, Module, ShadowModule, ModuleBase, NavMenuItemMediaMixin
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import delete_all_apps
from corehq.apps.app_manager.views.utils import (
    SHADOW_MODULE_PROPERTIES_TO_COPY,
    MODULE_BASE_PROPERTIES_TO_COPY,
    handle_shadow_child_modules,
)

EXPLANATION = """
    If we have a shadow module whose source module is a parent,
    handle_shadow_child_modules will automatically create shadows of the source
    module's child modules. If you're reading this, you probably added a new
    property to ModuleBase or ShadowModule. You need to declare whether this
    property should be automatically copied to these shadow child modules
    (add it to MODULE_BASE_PROPERTIES_TO_COPY or SHADOW_MODULE_PROPERTIES_TO_COPY),
    or excluded (add it to ignored_properties in this test).
"""


class HandleShadowChildModulesTest(TestCase):
    """Test how shadow child modules are created and deleted
    """

    def setUp(self):
        super().setUp()
        self.domain = "test-domain"

        self.factory = AppFactory(domain=self.domain)

        # m0
        self.basic_module, self.form0 = self.factory.new_basic_module("basic_module", "parrot")

        # m1
        self.child_module, form2 = self.factory.new_basic_module(
            "child_module", "parrot", parent_module=self.basic_module
        )
        self.child_module.put_in_root = True
        self.form3 = self.factory.new_form(self.child_module)

        # m2
        self.shadow_module = self.factory.new_shadow_module("shadow_module", self.basic_module, with_form=False)
        self.shadow_module.excluded_form_ids = [self.form0.unique_id, self.form3.unique_id]
        self.factory.app.save()

        self.app = self.factory.app

    def tearDown(self):
        delete_all_apps()
        super().tearDown()

    def test_creates_new_modules(self):

        handle_shadow_child_modules(self.app, self.app.get_module_by_unique_id(self.shadow_module.unique_id))

        app = Application.get(self.app.get_id)

        # A new shadow module should be created whose module source is the child
        self.assertEqual(len(app.modules), 4)
        self.assertEqual(app.modules[3].module_type, "shadow")
        self.assertEqual(app.modules[3].source_module_id, self.child_module.unique_id)

        # excluded form ids should move from the parent to the child module,
        # retaining the pertinent parent ids
        self.assertItemsEqual(app.modules[3].excluded_form_ids, [self.form3.unique_id])
        self.assertItemsEqual(
            app.get_module_by_unique_id(self.shadow_module.unique_id).excluded_form_ids,
            [self.form0.unique_id],
        )

        # Calling the command again should not make new modules
        shadow_child_module_id = app.modules[3].unique_id
        handle_shadow_child_modules(app, app.get_module_by_unique_id(self.shadow_module.unique_id))
        app = Application.get(app.get_id)
        self.assertEqual(len(app.modules), 4)
        self.assertEqual(app.modules[3].unique_id, shadow_child_module_id)

    def test_deletes_module_child_removed(self):
        # Create new module
        handle_shadow_child_modules(self.app, self.app.get_module_by_unique_id(self.shadow_module.unique_id))

        # Change child module's parent
        app = Application.get(self.app.get_id)
        app.modules[1].root_module_id = None
        app.save()

        # The new shadow module should be deleted, since it is no longer needed
        handle_shadow_child_modules(app, app.get_module_by_unique_id(self.shadow_module.unique_id))
        self.assertEqual(len(app.modules), 3)

    def test_deletes_module_source_changed(self):
        # Create new module
        handle_shadow_child_modules(self.app, self.app.get_module_by_unique_id(self.shadow_module.unique_id))

        # Change parent shadow module's source
        app = Application.get(self.app.get_id)
        new_module = Module.new_module("name", "en")
        app.add_module(new_module)
        app.get_module_by_unique_id(self.shadow_module.unique_id).source_module_id = new_module.unique_id
        app.save()
        self.assertEqual(len(app.modules), 5)

        # Child shadow module should be removed
        handle_shadow_child_modules(app, app.get_module_by_unique_id(self.shadow_module.unique_id))
        self.assertEqual(len(app.modules), 4)

    def test_shadow_source_is_child(self):
        # If the source is a child, the parent of the shadow should be the same as the source
        shadow_child = self.factory.new_shadow_module("shadow_child_module", self.child_module, with_form=False)
        self.factory.app.save()

        handle_shadow_child_modules(self.app, self.app.get_module_by_unique_id(shadow_child.unique_id))

        app = Application.get(self.app.get_id)
        shadow_child = app.get_module_by_unique_id(shadow_child.unique_id)
        self.assertEqual(shadow_child.root_module_id, self.child_module.root_module_id)

        # change the source
        shadow_child.source_module_id = self.basic_module.unique_id
        app.save()

        handle_shadow_child_modules(app, app.get_module_by_unique_id(shadow_child.unique_id))

        app = Application.get(self.app.get_id)
        shadow_child = app.get_module_by_unique_id(shadow_child.unique_id)
        self.assertIsNone(shadow_child.root_module_id)

    def test_all_shadow_module_properties_set(self):
        ignored_properties = [
            "module_type",
            "source_module_id",
            "doc_type",
            "_root_module_id",
            "forms",
            "excluded_form_ids",
            "shadow_module_version",
            "session_endpoint_id",
            "case_list_session_endpoint_id",
            "form_session_endpoints",
        ]
        required_properties = {
            prop
            for prop in vars(ShadowModule)
            if isinstance(vars(ShadowModule)[prop], jsonobject.base_properties.JsonProperty)
            and prop not in ignored_properties
        }
        copied_properties = {prop for prop, _ in SHADOW_MODULE_PROPERTIES_TO_COPY}

        unexpected_properties = required_properties - copied_properties
        msg = f"Unexpected properties {unexpected_properties}\n{EXPLANATION}"
        self.assertItemsEqual(unexpected_properties, [], msg)

    def test_all_base_module_properties_set(self):
        ignored_properties = [
            "doc_type",
            "root_module_id",
            "name",
            "case_type",
            "unique_id",
            "session_endpoint_id",
            "case_list_session_endpoint_id",
            "custom_assertions",
        ]
        required_properties = {
            prop
            for prop in vars(ModuleBase)
            if isinstance(vars(ModuleBase)[prop], jsonobject.base_properties.JsonProperty)
            and prop not in ignored_properties
        }
        required_properties |= {
            prop
            for prop in vars(NavMenuItemMediaMixin)
            if isinstance(vars(NavMenuItemMediaMixin)[prop], jsonobject.base_properties.JsonProperty)
            and prop not in ignored_properties
        }

        copied_properties = {prop for prop, _ in MODULE_BASE_PROPERTIES_TO_COPY}
        unexpected_properties = required_properties - copied_properties
        msg = f"Unexpected properties {unexpected_properties}\n{EXPLANATION}"
        self.assertItemsEqual(unexpected_properties, [], msg)
