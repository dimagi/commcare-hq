from django.test import SimpleTestCase

from corehq.apps.app_manager.management.commands.migrate_case_list_custom_variables import Command


class CaseListCustomVariablesTests(SimpleTestCase):

    custom_variables_xml = "<xml1 function=\"if(true(), 'text text', '')\"/>\n<xml2 function=\"text\"/>"
    custom_variables_dict = {"xml1": "if(true(), 'text text', '')", "xml2": "text"}

    def make_module(self, short_dict):
        return {
            "case_details": {
                "short": short_dict,
                "long": {}
            }
        }

    def make_app(self, short_dict):
        return {
            "modules": [
                self.make_module(short_dict)
            ]
        }

    def test_parse(self):
        var_dict = Command.parse(CaseListCustomVariablesTests.custom_variables_xml)
        self.assertEqual(var_dict, CaseListCustomVariablesTests.custom_variables_dict)

    def test_migrate_details_forward(self):
        detail = {
            "custom_variables": CaseListCustomVariablesTests.custom_variables_xml,
        }

        did_migrate = Command.migrate_detail_forward(detail)
        self.assertTrue(did_migrate)
        self.assertIsNotNone(detail.get("custom_variables_dict"))
        self.assertTrue(detail.get("custom_variables_dict"), CaseListCustomVariablesTests.custom_variables_dict)
        self.assertIsNotNone(detail.get("custom_variables"))

    def test_migrate_details_forward_no_variables(self):
        detail = {}
        did_migrate = Command.migrate_detail_forward(detail)
        self.assertFalse(did_migrate)

    def test_migrate_details_backward(self):
        detail = {
            "custom_variables": CaseListCustomVariablesTests.custom_variables_xml,
            "custom_variables_dict": CaseListCustomVariablesTests.custom_variables_dict,
        }

        did_migrate = Command.migrate_detail_backward(detail)
        self.assertTrue(did_migrate)
        self.assertIsNotNone(detail.get("custom_variables"))
        self.assertTrue(detail.get("custom_variables"), CaseListCustomVariablesTests.custom_variables_xml)
        self.assertIsNone(detail.get("custom_variables_dict"))

    def test_migrate_app_impl(self):
        app = self.make_app({"custom_variables": CaseListCustomVariablesTests.custom_variables_xml})
        migrated_app = Command.migrate_app_impl(app, False)
        self.assertIsNotNone(migrated_app)
        self.assertEqual(
            migrated_app,
            self.make_app({
                "custom_variables": CaseListCustomVariablesTests.custom_variables_xml,
                "custom_variables_dict": CaseListCustomVariablesTests.custom_variables_dict
            })
        )

    def test_migrate_app_impl_multiple_modules(self):
        app = {
            "modules": [
                self.make_module({"custom_variables": CaseListCustomVariablesTests.custom_variables_xml}),
                self.make_module({})
            ]
        }

        migrated_app = Command.migrate_app_impl(app, False)
        self.assertIsNotNone(migrated_app)
        self.assertEqual(
            migrated_app,
            {
                "modules": [
                    self.make_module({
                        "custom_variables": CaseListCustomVariablesTests.custom_variables_xml,
                        "custom_variables_dict": CaseListCustomVariablesTests.custom_variables_dict
                    }),
                    self.make_module({})
                ]
            }
        )

    def test_migrate_app_impl_no_change(self):
        app = self.make_app({})
        migrated_app = Command.migrate_app_impl(app, False)
        self.assertIsNone(migrated_app)

    def test_migrate_app_impl_reverse(self):
        app = self.make_app({
            "custom_variables": CaseListCustomVariablesTests.custom_variables_xml,
            "custom_variables_dict": CaseListCustomVariablesTests.custom_variables_dict
        })
        migrated_app = Command.migrate_app_impl(app, True)
        self.assertIsNotNone(migrated_app)
        self.assertEqual(
            migrated_app,
            self.make_app({"custom_variables": CaseListCustomVariablesTests.custom_variables_xml})
        )
