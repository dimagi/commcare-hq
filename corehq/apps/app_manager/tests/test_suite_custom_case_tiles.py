from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    DetailColumn,
    Module,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)


def add_columns_for_case_details(_module, field='a', format='plain', useXpathExpression=False):
    column = DetailColumn(
        header={'en': 'a'},
        model='case',
        field=field,
        format=format,
        grid_x=1,
        grid_y=1,
        width=3,
        height=1,
        show_border=False,
        show_shading=False)
    column.useXpathExpression = useXpathExpression
    _module.case_details.short.columns = [
        column,
    ]


@patch_get_xform_resource_overrides()
class SuiteCustomCaseTilesTest(SimpleTestCase, SuiteMixin):

    def test_custom_case_tile(self, *args):
        app = Application.new_app('domain', 'Untitled Application')
        from corehq.apps.builds.models import BuildSpec
        app.build_spec = BuildSpec.from_string('2.7.0/latest')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = "custom"
        module.case_details.short.display = "short"
        add_columns_for_case_details(module, "concat('a')", "clickable-icon", True)

        suite = app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <field>
                    <style show-border="false" show-shading="false">
                        <grid grid-height="1" grid-width="3" grid-x="1" grid-y="1"/>
                    </style>
                    <header width="13%">
                        <text>
                            <locale id="m0.case_short.case_calculated_property_1.header"/>
                        </text>
                    </header>
                    <template form="clickable-icon" width="13%">
                        <text>
                            <xpath function="''">
                                <variable name="calculated_property">
                                    <xpath function="concat('a')"/>
                                </variable>
                            </xpath>
                        </text>
                    </template>
                    <sort direction="ascending" order="1" type="string">
                        <text>
                            <xpath function="''">
                                <variable name="calculated_property">
                                    <xpath function="concat('a')"/>
                                </variable>
                            </xpath>
                        </text>
                    </sort>
                    <alt_text>
                        <text>
                            <xpath function="''"/>
                        </text>
                    </alt_text>
                </field>
            </partial>
            """,
            suite,
            "./detail[@id='m0_case_short']/field[1]"
        )

        self.assertXmlDoesNotHaveXpath(suite, "./detail[@id='m0_case_short']/field[2]")

    def test_custom_case_tile_address(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = "custom"
        add_columns_for_case_details(module, format='address')

        self.assertXmlPartialEqual(
            """
            <partial>
                <field>
                    <style show-border="false" show-shading="false">
                        <grid grid-height="1" grid-width="3" grid-x="1" grid-y="1"/>
                    </style>
                    <header>
                        <text>
                            <locale id="m0.case_short.case_a_1.header"/>
                        </text>
                    </header>
                    <template form="address">
                        <text>
                          <xpath function="a"/>
                        </text>
                    </template>
                </field>
            </partial>
            """,
            app.create_suite(),
            "./detail[@id='m0_case_short']/field[1]"
        )

    def test_custom_case_tile_empty_style(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = "custom"
        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'a'},
                model='case',
                field='a',
                format='plain'
            ),
        ]

        self.assertXmlPartialEqual(
            """
            <partial>
                <field>
                    <header>
                        <text>
                            <locale id="m0.case_short.case_a_1.header"/>
                        </text>
                    </header>
                    <template>
                        <text>
                          <xpath function="a"/>
                        </text>
                    </template>
                </field>
            </partial>
            """,
            app.create_suite(),
            "./detail[@id='m0_case_short']/field[1]"
        )
