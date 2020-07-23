import tempfile
import csv

from django.core.management import call_command
from django.test import TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import delete_all_apps


class CreateShadowChildrenTest(TestCase):
    """Test the create_shadow_children and find_shadow_children management commands
    """

    def setUp(self):
        super().setUp()
        self.domain = "test-domain"

    def tearDown(self):
        delete_all_apps()
        super().tearDown()

    def test_command_creates_new_modules(self):
        factory = AppFactory(domain=self.domain)

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

        call_command("create_shadow_children", domain=self.domain)

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

        # Calling the command again should not make new modules
        call_command("create_shadow_children", domain=self.domain)
        app = Application.get(factory.app.get_id)
        self.assertEqual(len(app.modules), 4)

    def test_command_finds_apps(self):
        factory = AppFactory(domain=self.domain)

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

        factory2 = AppFactory(domain=self.domain)
        basic_module, form0 = factory2.new_basic_module("basic_module", "parrot")
        shadow_module = factory2.new_shadow_module("shadow_module", basic_module, with_form=False)
        factory2.app.save()

        fd, path = tempfile.mkstemp()
        call_command("find_shadow_children", csv_path=path)

        with open(fd, "r") as f:
            reader = csv.DictReader(f)
            lines = [l for l in reader]

        self.assertEqual(1, len(lines))
        self.assertEqual(factory.app.get_id, lines[0]["app_id"])
        self.assertEqual("['child_module module']", lines[0]["unmigrated_modules"])

        # Migrating the app should remove it from the list
        call_command("create_shadow_children")

        fd, path = tempfile.mkstemp()
        call_command("find_shadow_children", csv_path=path)

        with open(fd, "r") as f:
            reader = csv.DictReader(f)
            lines = [l for l in reader]

        self.assertEqual(0, len(lines))
