from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    Module, CaseTileGroupConfig, )
from corehq.apps.app_manager.suite_xml.features.case_tiles import CaseTileTemplates
from corehq.apps.app_manager.tests.test_suite_case_tiles import add_columns_for_case_details
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteCaseTilesGroupingTest(SimpleTestCase, SuiteMixin):
    file_path = ('data',)

    def test_case_tiles_with_grouping(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module)
        module.case_details.short.case_tile_group = CaseTileGroupConfig(
            index_identifier="parent", header_rows=3
        )

        module.assign_references()

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        self.assertDetailGroup(app.create_suite(), "m0_case_short", header_rows=3)

    def assertDetailGroup(self, suite_xml, detail_id, index_identifier="parent", header_rows=1):
        self.assertXmlPartialEqual(
            f"""
            <partial>
               <group function="./index/{index_identifier}" header-rows="{header_rows}"/>
            </partial>
            """,
            suite_xml,
            f"detail[@id='{detail_id}']/group",
        )
