from django.test import SimpleTestCase

from corehq.apps.app_manager.const import CASE_LIST_FILTER_LOCATIONS_FIXTURE
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteAssertionsTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_fixture_to_case_selection(self, *args):
        factory = AppFactory(build_version='2.9.0')

        module, form = factory.new_basic_module('my_module', 'cases')
        module.fixture_select.active = True
        module.fixture_select.fixture_type = 'days'
        module.fixture_select.display_column = 'my_display_column'
        module.fixture_select.variable_column = 'my_variable_column'
        module.fixture_select.xpath = 'date(scheduled_date) <= date(today() + $fixture_value)'

        factory.form_requires_case(form)

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection'), factory.app.create_suite())

    def test_location_fixture_type(self, *args):
        factory = AppFactory(build_version='2.9.0')

        module, form = factory.new_basic_module('my_module', 'cases')
        module.fixture_select.active = True
        module.fixture_select.fixture_type = CASE_LIST_FILTER_LOCATIONS_FIXTURE
        module.fixture_select.display_column = 'name'
        module.fixture_select.variable_column = '@id'
        module.fixture_select.xpath = 'case_location_id=$fixture_value'

        factory.form_requires_case(form)

        suite_xml = factory.app.create_suite()

        expected_xml = """
            <partial>
                <datum detail-select="m0_fixture_select" id="fixture_value_m0"
                  nodeset="instance('locations')/locations/location" value="@id"/>
            </partial>
        """
        self.assertXmlPartialEqual(expected_xml, suite_xml, "./entry/session/datum[1]")

        # ensure locations fixture is included
        self.assertXmlPartialEqual(
            '<partial><instance id="locations" src="jr://fixture/locations"/></partial>',
            suite_xml,
            "./entry/instance[3]"
        )

    def test_fixture_to_case_selection_with_form_filtering(self, *args):
        factory = AppFactory(build_version='2.9.0')

        module, form = factory.new_basic_module('my_module', 'cases')
        module.fixture_select.active = True
        module.fixture_select.fixture_type = 'days'
        module.fixture_select.display_column = 'my_display_column'
        module.fixture_select.variable_column = 'my_variable_column'
        module.fixture_select.xpath = 'date(scheduled_date) <= date(today() + $fixture_value)'

        factory.form_requires_case(form)

        form.form_filter = "$fixture_value <= today()"

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection-with-form-filtering'),
                            factory.app.create_suite())

    def test_fixture_to_case_selection_localization(self, *args):
        factory = AppFactory(build_version='2.9.0')

        module, form = factory.new_basic_module('my_module', 'cases')
        module.fixture_select.active = True
        module.fixture_select.fixture_type = 'days'
        module.fixture_select.display_column = 'my_display_column'
        module.fixture_select.localize = True
        module.fixture_select.variable_column = 'my_variable_column'
        module.fixture_select.xpath = 'date(scheduled_date) <= date(today() + $fixture_value)'

        factory.form_requires_case(form)

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection-localization'), factory.app.create_suite())

    def test_fixture_to_case_selection_parent_child(self, *args):
        factory = AppFactory(build_version='2.9.0')

        m0, m0f0 = factory.new_basic_module('parent', 'parent')
        m0.fixture_select.active = True
        m0.fixture_select.fixture_type = 'province'
        m0.fixture_select.display_column = 'display_name'
        m0.fixture_select.variable_column = 'var_name'
        m0.fixture_select.xpath = 'province = $fixture_value'

        factory.form_requires_case(m0f0)

        m1, m1f0 = factory.new_basic_module('child', 'child')
        m1.fixture_select.active = True
        m1.fixture_select.fixture_type = 'city'
        m1.fixture_select.display_column = 'display_name'
        m1.fixture_select.variable_column = 'var_name'
        m1.fixture_select.xpath = 'city = $fixture_value'

        factory.form_requires_case(m1f0, parent_case_type='parent')

        self.assertXmlEqual(self.get_xml('fixture-to-case-selection-parent-child'), factory.app.create_suite())
