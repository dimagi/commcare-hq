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


def add_columns_for_case_details(_module, format='plain'):
    _module.case_details.short.columns = [
        DetailColumn(
            header={'en': 'a'},
            model='case',
            field='a',
            format=format,
            grid_x=1,
            grid_y=1,
            width=3,
            height=1
        ),
    ]


@patch_get_xform_resource_overrides()
class SuiteCustomCaseTilesTest(SimpleTestCase, SuiteMixin):

    def test_custom_case_tile(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = "custom"
        add_columns_for_case_details(module)

        self.assertXmlPartialEqual(
            """
            <partial>
                <field>
                    <style>
                        <grid grid-height="1" grid-width="3" grid-x="1" grid-y="1"/>
                    </style>
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
                    <style>
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
