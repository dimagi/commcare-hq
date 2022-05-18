from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchProperty,
    SortElement,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteSortingTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_multisort_suite(self, *args):
        self._test_generic_suite('multi-sort', 'multi-sort')

    def test_sort_only_value_suite(self, *args):
        self._test_generic_suite('sort-only-value', 'sort-only-value')
        self._test_app_strings('sort-only-value')

    def test_sort_cache_suite(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        detail = app.modules[0].case_details.short
        detail.sort_elements.append(
            SortElement(
                field=detail.columns[0].field,
                type='index',
                direction='descending',
                blanks='first',
            )
        )
        self.assertXmlPartialEqual(
            self.get_xml('sort-cache'),
            app.create_suite(),
            "./detail[@id='m0_case_short']"
        )

    def test_sort_cache_search(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        app.modules[0].search_config = CaseSearch(
            properties=[CaseSearchProperty(name='name', label={'en': 'Name'})],
        )
        detail = app.modules[0].case_details.short
        detail.sort_elements.append(
            SortElement(
                field=detail.columns[0].field,
                type='index',
                direction='descending',
                blanks='first',
            )
        )

        # wrap to have assign_references called
        app = Application.wrap(app.to_json())

        self.assertXmlPartialEqual(
            self.get_xml('sort-cache-search'),
            app.create_suite(),
            "./detail[@id='m0_search_short']"
        )

    def test_sort_calculation(self, *args):
        app = Application.wrap(self.get_json('suite-advanced'))
        detail = app.modules[0].case_details.short
        detail.sort_elements.append(
            SortElement(
                field=detail.columns[0].field,
                type='string',
                direction='descending',
                blanks='first',
                sort_calculation='random()'
            )
        )
        sort_node = """
        <partial>
            <sort direction="descending" blanks="first" order="1" type="string">
              <text>
                <xpath function="random()"/>
              </text>
            </sort>
        </partial>
        """
        self.assertXmlPartialEqual(
            sort_node,
            app.create_suite(),
            "./detail[@id='m0_case_short']/field/sort"
        )
