from django.test import TestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import delete_all_apps
from corehq.apps.app_manager.views.utils import handle_shadow_child_modules


class HandleShadowChildModulesTest(TestCase):
    """Test how shadow child modules are created and deleted
    """

    def setUp(self):
        super().setUp()
        self.domain = "test-domain"

        factory = AppFactory(domain=self.domain)

        # m0
        basic_module, self.form0 = factory.new_basic_module("basic_module", "parrot")
        form1 = factory.new_form(basic_module)

        # m1
        self.child_module, form2 = factory.new_basic_module(
            "child_module", "parrot", parent_module=basic_module
        )
        self.child_module.put_in_root = True
        self.form3 = factory.new_form(self.child_module)

        # m2
        self.shadow_module = factory.new_shadow_module("shadow_module", basic_module, with_form=False)
        self.shadow_module.excluded_form_ids = [self.form0.unique_id, self.form3.unique_id]
        factory.app.save()

        self.app = factory.app

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
        handle_shadow_child_modules(app, app.get_module_by_unique_id(self.shadow_module.unique_id))
        app = Application.get(app.get_id)
        self.assertEqual(len(app.modules), 4)

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
