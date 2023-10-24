from django.test import SimpleTestCase

from corehq.apps.app_manager.management.commands.delete_case_list_custom_variables_xml import Command


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

    def test_serialize(self):
        xml = Command.serialize(CaseListCustomVariablesTests.custom_variables_dict)
        self.assertEqual(xml, CaseListCustomVariablesTests.custom_variables_xml)

    def test_delete_xml(self):
        detail = {
            "custom_variables": CaseListCustomVariablesTests.custom_variables_xml,
        }

        did_migrate = Command.delete_xml(detail)
        self.assertTrue(did_migrate)
        self.assertIsNone(detail.get("custom_variables"))

    def test_recreate_xml(self):
        detail = {
            "custom_variables_dict": CaseListCustomVariablesTests.custom_variables_dict,
        }
        did_migrate = Command.recreate_xml(detail)
        self.assertTrue(did_migrate)
        self.assertIsNotNone(detail.get("custom_variables"))
        self.assertEqual(detail.get("custom_variables"), CaseListCustomVariablesTests.custom_variables_xml)
