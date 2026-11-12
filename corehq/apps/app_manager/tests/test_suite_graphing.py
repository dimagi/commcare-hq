from django.test import SimpleTestCase

from lxml.etree import tostring

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.suite_xml.xml_models import (
    ConfigurationGroup,
    ConfigurationItem,
    Detail,
    Field,
    Graph,
    GraphTemplate,
    Series,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    parse_normalize,
    patch_get_xform_resource_overrides,
)
from corehq.tests.util.xml import assert_xml_equal


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

        expect = [tostring(text_element) for text_element in expected_configuration]
        actual = [tostring(text_element) for text_element in actual_configuration]
        assert sorted(expect) == sorted(actual)

        expected_suite.find('detail/field/template/graph').remove(expected_configuration)
        actual_suite.find('detail/field/template/graph').remove(actual_configuration)

        assert_xml_equal(tostring(expected_suite), tostring(actual_suite))

    def test_get_all_xpaths_includes_graph_field_xpaths(self, *args):
        template = GraphTemplate(
            form='graph',
            graph=Graph(
                type='xy',
                series=[
                    Series(
                        nodeset="instance('casedb')/casedb/case",
                        configuration=ConfigurationGroup(configs=[
                            ConfigurationItem(id='color', xpath_function="'blue'"),
                        ]),
                    ),
                ],
                configuration=ConfigurationGroup(configs=[
                    ConfigurationItem(id='title', xpath_function="'My Graph'"),
                ]),
            ),
        )
        detail = Detail(fields=[Field(template=template)])

        assert detail.get_all_xpaths() == {
            "'My Graph'",
            "instance('casedb')/casedb/case",
            "'blue'",
        }
