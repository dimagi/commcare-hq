from django.test import SimpleTestCase

from lxml.etree import tostring

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    parse_normalize,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteGraphingTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_graphing(self, *args):
        self._test_generic_suite('app_graphing', 'suite-graphing')

    def test_fixtures_in_graph(self, *args):
        expected_suite = parse_normalize(self.get_xml('suite-fixture-graphing'), to_string=False)
        actual_suite = parse_normalize(
            Application.wrap(self.get_json('app_fixture_graphing')).create_suite(), to_string=False)

        expected_configuration_list = expected_suite.findall('detail/field/template/graph/configuration')
        actual_configuration_list = actual_suite.findall('detail/field/template/graph/configuration')

        self.assertEqual(len(expected_configuration_list), 1)
        self.assertEqual(len(actual_configuration_list), 1)

        expected_configuration = expected_configuration_list[0]
        actual_configuration = actual_configuration_list[0]

        self.assertItemsEqual(
            [tostring(text_element) for text_element in expected_configuration],
            [tostring(text_element) for text_element in actual_configuration]
        )

        expected_suite.find('detail/field/template/graph').remove(expected_configuration)
        actual_suite.find('detail/field/template/graph').remove(actual_configuration)

        self.assertXmlEqual(tostring(expected_suite), tostring(actual_suite))
