from django.test import TestCase
from django.core.management import call_command


from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.app_factory import AppFactory


class CreateShadowChildrenTest(TestCase):
    """Test the create_shadow_childrent management command
    """

    def test_command_creates_new_modules(self):
        domain = "test-domain"
        factory = AppFactory(domain=domain)

        # m0
        basic_module, form0 = factory.new_basic_module("basic_module", "parrot")
        form0.xmlns = "http://openrosa.org/formdesigner/m0f0"
        form1 = factory.new_form(basic_module)
        form1.xmlns = "http://openrosa.org/formdesigner/m0f1"

        # m1
        child_module, form2 = factory.new_basic_module(
            "child_module", "parrot", parent_module=basic_module
        )
        form2.xmlns = "http://openrosa.org/formdesigner/m1f0"
        child_module.put_in_root = True
        form3 = factory.new_form(child_module)

        # m2
        shadow_module = factory.new_shadow_module("shadow_module", basic_module, with_form=False)
        shadow_module.excluded_form_ids = [form0.unique_id, form3.unique_id]
        factory.app.save()

        call_command("create_shadow_children", domain=domain)
        app = Application.get(factory.app.get_id)

        # A new shadow module should be created whose module source is the child
        self.assertEqual(len(app.modules), 4)
        self.assertEqual(app.modules[3].module_type, "shadow")
        self.assertEqual(app.modules[3].source_module_id, child_module.unique_id)

        # excluded form ids should move from the parent to the child module,
        # retaining the pertinent parent ids
        self.assertItemsEqual(app.modules[3].excluded_form_ids, [form3.unique_id])
        self.assertItemsEqual(
            app.get_module_by_unique_id(shadow_module.unique_id).excluded_form_ids,
            [form0.unique_id],
        )
