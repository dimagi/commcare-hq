from uuid import uuid4
from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    Form,
    ShadowFormEndpoint,
    ShadowModule
)
from corehq.apps.app_manager.views.utils import (
    _duplicate_endpoint_ids,
    get_cleaned_session_endpoint_id,
    get_cleaned_and_deduplicated_session_endpoint_id,
    set_shadow_module_and_form_session_endpoint
)

from corehq.apps.app_manager.exceptions import AppMisconfigurationError


class TestSessionEndpointUtils(SimpleTestCase):
    new_endpoint = "abc"

    normal_module_session_endpoint_id = "nmsei"
    form_unique_id = "fui"
    form_session_endpoint_id = "fsei"
    shadow_module_session_endpoint_id = "smsei"
    shadow_form_session_endpoint_id = "sfsei"

    def create_fixtures(self):
        form = Form(
            unique_id=self.form_unique_id,
            session_endpoint_id=self.form_session_endpoint_id
        )

        normal_module = AdvancedModule(
            unique_id="normal_module",
            session_endpoint_id=self.normal_module_session_endpoint_id,
            forms=[form]
        )

        shadow_module = ShadowModule(
            unique_id="shadow_module",
            session_endpoint_id=self.shadow_module_session_endpoint_id,
            form_session_endpoints=[
                ShadowFormEndpoint(
                    form_id=self.form_unique_id,
                    session_endpoint_id=self.shadow_form_session_endpoint_id)
            ]
        )

        app = Application(
            modules=[normal_module, shadow_module]
        )

        return app, normal_module, shadow_module, form

    def _is_duplicate_endpoint_id(self, new_id, old_id, app):
        if not new_id or new_id == old_id:
            return False

        duplicates = _duplicate_endpoint_ids(new_id, [], None, app)
        return len(duplicates) > 0

    def test_is_duplicate_endpoint_id_no_change_false(self):
        app, _, _, _ = self.create_fixtures()
        is_duplicate = self._is_duplicate_endpoint_id(
            self.normal_module_session_endpoint_id, self.normal_module_session_endpoint_id, app)
        self.assertFalse(is_duplicate)

    def test_is_duplicate_endpoint_id_same_as_other_module_false(self):
        app, _, _, _ = self.create_fixtures()
        is_duplicate = self._is_duplicate_endpoint_id(
            self.shadow_module_session_endpoint_id, self.normal_module_session_endpoint_id, app)
        self.assertTrue(is_duplicate)

    def test_is_duplicate_endpoint_id_same_as_form_false(self):
        app, _, _, _ = self.create_fixtures()
        is_duplicate = self._is_duplicate_endpoint_id(
            self.form_session_endpoint_id, self.normal_module_session_endpoint_id, app)
        self.assertTrue(is_duplicate)

    def test_is_duplicate_endpoint_id_same_as_shadow_form_false(self):
        app, _, _, _ = self.create_fixtures()
        is_duplicate = self._is_duplicate_endpoint_id(
            self.shadow_form_session_endpoint_id, self.normal_module_session_endpoint_id, app)
        self.assertTrue(is_duplicate)

    def test_get_cleaned_session_endpoint_id(self):

        cleaned_endpoint = get_cleaned_session_endpoint_id(self.new_endpoint)

        self.assertEqual(self.new_endpoint, cleaned_endpoint)

        self.assertRaises(
            AppMisconfigurationError,
            lambda: get_cleaned_session_endpoint_id("abc;")
        )

    def test_get_cleaned_and_deduplicated_session_endpoint_id(self):
        app, normal_module, _, _ = self.create_fixtures()

        # Setting id to new id is ok
        deduplicated_endpoint = get_cleaned_and_deduplicated_session_endpoint_id(
            normal_module, self.new_endpoint, app)
        self.assertEqual(self.new_endpoint, deduplicated_endpoint)

        # Setting id to same id is ok
        deduplicated_endpoint = get_cleaned_and_deduplicated_session_endpoint_id(
            normal_module, self.normal_module_session_endpoint_id, app)
        self.assertEqual(self.normal_module_session_endpoint_id, deduplicated_endpoint)

        # Setting id to id used by other module fails
        self.assertRaises(
            AppMisconfigurationError,
            lambda: get_cleaned_and_deduplicated_session_endpoint_id(
                normal_module, self.shadow_module_session_endpoint_id, app)
        )

        # Setting id to id used by form fails
        self.assertRaises(
            AppMisconfigurationError,
            lambda: get_cleaned_and_deduplicated_session_endpoint_id(
                normal_module, self.form_session_endpoint_id, app)
        )

        # Setting id to id used by shadow form fails
        self.assertRaises(
            AppMisconfigurationError,
            lambda: get_cleaned_and_deduplicated_session_endpoint_id(
                normal_module, self.shadow_form_session_endpoint_id, app)
        )

    def test_set_shadow_module_and_form_session_endpoint_new_value_for_module_ok(self):
        app, _, shadow_module, _ = self.create_fixtures()

        set_shadow_module_and_form_session_endpoint(
            shadow_module,
            self.new_endpoint,
            [{"form_id": self.form_unique_id, "session_endpoint_id": self.shadow_form_session_endpoint_id}],
            app
        )

        self.assertEqual(shadow_module.session_endpoint_id, self.new_endpoint)

    def test_set_shadow_module_and_form_session_endpoint_same_value_for_module_ok(self):
        app, _, shadow_module, _ = self.create_fixtures()

        set_shadow_module_and_form_session_endpoint(
            shadow_module,
            self.shadow_module_session_endpoint_id,
            [{"form_id": self.form_unique_id, "session_endpoint_id": self.shadow_form_session_endpoint_id}],
            app
        )

        self.assertEqual(shadow_module.session_endpoint_id, self.shadow_module_session_endpoint_id)

    def test_set_shadow_module_and_form_session_endpoint_other_modules_value_for_module_fails(self):
        app, _, shadow_module, _ = self.create_fixtures()

        self.assertRaises(
            AppMisconfigurationError,
            lambda: set_shadow_module_and_form_session_endpoint(
                shadow_module,
                self.normal_module_session_endpoint_id,
                [{"form_id": self.form_unique_id, "session_endpoint_id": self.shadow_form_session_endpoint_id}],
                app
            )
        )

    def test_set_shadow_module_and_form_session_endpoint_forms_value_for_module_fails(self):
        app, _, shadow_module, _ = self.create_fixtures()

        self.assertRaises(
            AppMisconfigurationError,
            lambda: set_shadow_module_and_form_session_endpoint(
                shadow_module,
                self.form_session_endpoint_id,
                [{"form_id": self.form_unique_id, "session_endpoint_id": self.shadow_form_session_endpoint_id}],
                app
            )
        )

    def test_set_shadow_module_and_form_session_endpoint_shadow_forms_value_for_module_fails(self):
        app, _, shadow_module, _ = self.create_fixtures()

        self.assertRaises(
            AppMisconfigurationError,
            lambda: set_shadow_module_and_form_session_endpoint(
                shadow_module,
                self.shadow_form_session_endpoint_id,
                [{"form_id": self.form_unique_id, "session_endpoint_id": self.shadow_form_session_endpoint_id}],
                app
            )
        )

    def test_set_shadow_module_and_form_session_endpoint_empty_form_endpoint_id_ignored(self):
        app, _, shadow_module, _ = self.create_fixtures()

        set_shadow_module_and_form_session_endpoint(
            shadow_module,
            self.new_endpoint,
            [{"form_id": self.form_unique_id, "session_endpoint_id": ""}],
            app
        )

        self.assertEqual(shadow_module.session_endpoint_id, self.new_endpoint)
        self.assertEqual(shadow_module.form_session_endpoints, [])

    def test_set_shadow_module_and_form_session_endpoint_form_endpoint_id_ok(self):
        app, _, shadow_module, _ = self.create_fixtures()

        set_shadow_module_and_form_session_endpoint(
            shadow_module,
            self.shadow_module_session_endpoint_id,
            [{"form_id": self.form_unique_id, "session_endpoint_id": self.new_endpoint}],
            app
        )

        self.assertEqual(shadow_module.session_endpoint_id, self.shadow_module_session_endpoint_id)
        self.assertEqual(
            shadow_module.form_session_endpoints,
            [ShadowFormEndpoint(form_id=self.form_unique_id, session_endpoint_id=self.new_endpoint)])

    def test_set_shadow_module_and_form_session_endpoint_used_twice(self):
        app, _, shadow_module, _ = self.create_fixtures()
        self.assertRaises(
            AppMisconfigurationError,
            lambda: set_shadow_module_and_form_session_endpoint(
                shadow_module,
                self.new_endpoint,
                [{"form_id": self.form_unique_id, "session_endpoint_id": self.new_endpoint}],
                app
            )
        )

    def test_set_shadow_module_and_form_session_endpoint_used_twice_in_forms(self):
        app, _, shadow_module, _ = self.create_fixtures()
        self.assertRaises(
            AppMisconfigurationError,
            lambda: set_shadow_module_and_form_session_endpoint(
                shadow_module,
                self.shadow_module_session_endpoint_id,
                [
                    {"form_id": self.form_unique_id, "session_endpoint_id": self.new_endpoint},
                    {"form_id": self.form_unique_id, "session_endpoint_id": self.new_endpoint}
                ],
                app
            )
        )

    def test_no_duplicates_in_other_places(self):
        app, module, _, _ = self.create_fixtures()
        module.forms.append(Form(
            unique_id=str(uuid4()),
            # this endpoint ID conflicts with the other form
            session_endpoint_id=self.form_session_endpoint_id,
        ))
        # no meaningful change to `module`, but the duplicates should be caught
        duplicates = _duplicate_endpoint_ids(
            module.session_endpoint_id, [], module.unique_id, app
        )
        self.assertEqual(duplicates, [self.form_session_endpoint_id])
