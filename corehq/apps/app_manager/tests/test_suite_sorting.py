from django.test import SimpleTestCase

from corehq import privileges
from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchProperty,
    DetailColumn,
    MappingItem,
    SortElement,
)

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)
from corehq.util.test_utils import privilege_enabled


@patch_get_xform_resource_overrides()
class SuiteSortingTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_multisort_suite(self, *args):
        self._test_generic_suite('multi-sort', 'multi-sort')

    @privilege_enabled(privileges.APP_DEPENDENCIES)
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

    def test_calculated_property_as_sort_property(self):
        factory = AppFactory(build_version='2.3.0')
        module, form = factory.new_basic_module("my_module", "person")
        factory.form_requires_case(form)

        module.case_details.short.display = 'short'
        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'a'},
                model='case',
                field='a',
                format='plain',
                case_tile_field='header'
            ),
            DetailColumn(
                header={'en': 'is bob'},
                model='case',
                field='name = "bob"',
                useXpathExpression=True,
                format='plain',
            ),
            DetailColumn(
                header={'en': 'is old'},
                model='case',
                field='age > 40',
                useXpathExpression=True,
                format='plain',
            ),
        ]

        module.case_details.short.sort_elements = [
            SortElement(
                field='a',
                type='index',
                direction='descending',
                blanks='first',
            ),
            SortElement(
                field='_cc_calculated_2',
                type='index',
                direction='descending',
                blanks='first',
            ),
            SortElement(
                field='_cc_calculated_1',
                type='index',
                direction='descending',
                blanks='first',
            )
        ]

        suite = factory.app.create_suite()
        self.assertXmlDoesNotHaveXpath(suite, "detail/field/sort/text/xpath[@function='_cc_calculated_2']")

        self.assertXmlPartialEqual("""
        <partial>
            <field>
              <header>
                <text>
                  <locale id="m0.case_short.case_calculated_property_3.header"/>
                </text>
              </header>
              <template>
                <text>
                  <xpath function="$calculated_property">
                    <variable name="calculated_property">
                      <xpath function="age &gt; 40"/>
                    </variable>
                  </xpath>
                </text>
              </template>
              <sort type="string" order="-2" direction="descending" blanks="first">
                <text>
                  <xpath function="$calculated_property">
                    <variable name="calculated_property">
                      <xpath function="age &gt; 40"/>
                    </variable>
                  </xpath>
                </text>
              </sort>
            </field>
        </partial>
        """, suite, "detail[1]/field[3]")

    def test_calculated_property_with_translatable_text_as_sort_property(self):
        factory = AppFactory(build_version='2.3.0')
        module, form = factory.new_basic_module("my_module", None)
        factory.form_requires_case(form)

        module.case_details.short.display = 'short'
        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'a'},
                model='case',
                field='a',
                format='plain',
                case_tile_field='header'
            ),
            DetailColumn(
                header={'en': 'Fruit'},
                model='case',
                field='concat("3 ", $kfruit1)',
                format='translatable-enum',
                enum=[
                    MappingItem(key='fruit1', value={'en': 'Apple', 'es': 'Manzana'}),
                ],
            ),
        ]

        module.case_details.short.sort_elements = [
            SortElement(
                field='concat("3 ", $kfruit1)',
                type='string',
                direction='descending',
                blanks='first',
            )
        ]

        self.assertXmlPartialEqual("""
            <partial>
                <field>
                  <header>
                    <text>
                      <locale id="m0.case_short.case_concat(&quot;3 &quot;, $kfruit1)_2.header"/>
                    </text>
                  </header>
                  <template>
                    <text>
                      <xpath function="concat(&quot;3 &quot;, $kkfruit1)">
                        <variable name="kfruit1">
                          <locale id="m0.case_short.case_concat(&quot;3 &quot;, $kfruit1)_2.enum.kfruit1"/>
                        </variable>
                      </xpath>
                    </text>
                  </template>
                  <sort type="string" order="1" direction="descending" blanks="first">
                    <text>
                      <xpath function="concat(&quot;3 &quot;, $kkfruit1)">
                        <variable name="kfruit1">
                          <locale id="m0.case_short.case_concat(&quot;3 &quot;, $kfruit1)_2.enum.kfruit1"/>
                        </variable>
                      </xpath>
                    </text>
                  </sort>
                </field>
            </partial>
            """, factory.app.create_suite(), 'detail/field[2]')
