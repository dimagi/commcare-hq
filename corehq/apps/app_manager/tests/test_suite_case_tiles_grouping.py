from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    Module, CaseTileGroupConfig,
)
from corehq.apps.app_manager.suite_xml.features.case_tiles import CaseTileTemplates
from corehq.apps.app_manager.tests.test_suite_case_tiles import add_columns_for_case_details
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteCaseTilesGroupingTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_case_tiles_with_grouping(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module)
        module.case_details.short.case_tile_group = CaseTileGroupConfig(xpath_function="./index/parent")

        module.assign_references()

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        self.assertXmlPartialEqual(
            """
            <partial>
               <group function="./index/parent" grid-header-rows="1"/>
            </partial>
            """,
            app.create_suite(),
            "detail[@id='m0_case_short']/group",
        )

    def test_entry_datum_with_case_tile_grouping(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'child'
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module)
        module.case_details.short.case_tile_group = CaseTileGroupConfig(xpath_function="./index/parent")

        module.assign_references()

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        suite = app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
              <session>
                <datum 
                    detail-confirm="m0_case_long" 
                    detail-select="m0_case_short" 
                    id="case_id_child" 
                    nodeset="instance('casedb')/casedb/case[@case_type='child'][@status='open']" 
                    value="./@case_id"/>
                <datum function="./index/parent" id="case_id"/>
              </session>
            </partial>
            """,
            suite,
            "entry[1]/session",
        )
