from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    CaseTileGroupConfig, )
from corehq.apps.app_manager.suite_xml.features.case_tiles import CaseTileTemplates
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.test_suite_case_tiles import add_columns_for_case_details
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteCaseTilesGroupingTest(SimpleTestCase, SuiteMixin):
    file_path = ('data',)

    def test_case_tiles_with_grouping(self, *args):
        factory = AppFactory(build_version="2.54.0")

        module, form = factory.new_basic_module("patient", "patient")
        factory.form_requires_case(form)
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module)
        module.case_details.short.case_tile_group = CaseTileGroupConfig(
            index_identifier="parent", header_rows=3
        )

        module.assign_references()

        suite = factory.app.create_suite()
        self.assertDetailGroup(suite, "m0_case_short", header_rows=3)

        self.assertXmlPartialEqual(
            """
            <partial>
              <session>
                <datum
                    detail-confirm="m0_case_long"
                    detail-select="m0_case_short"
                    id="case_id"
                    nodeset="instance('casedb')/casedb/case[@case_type='patient'][@status='open']"
                    value="./@case_id" />
                <datum
                    function="join(' ', distinct-values(instance('casedb')/casedb/case[@case_id = instance('commcaresession')/session/data/case_id]/index/parent))"
                    id="case_id_parent_ids" />
              </session>
            </partial>""",
            suite,
            "entry[1]/session"
        )

    def test_case_tiles_with_grouping_multiselect(self, *args):
        factory = AppFactory(build_version="2.54.0")

        module, form = factory.new_basic_module("patient", "patient")
        factory.form_requires_case(form)
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module)
        module.case_details.short.case_tile_group = CaseTileGroupConfig(
            index_identifier="parent", header_rows=3
        )
        module.case_details.short.multi_select = True

        module.assign_references()

        suite = factory.app.create_suite()
        self.assertDetailGroup(suite, "m0_case_short", header_rows=3)

        self.assertXmlPartialEqual(
            """
            <partial>
              <session>
                <instance-datum
                    detail-confirm="m0_case_long"
                    detail-select="m0_case_short"
                    id="selected_cases"
                    nodeset="instance('casedb')/casedb/case[@case_type='patient'][@status='open']"
                    max-select-value="100"
                    value="./@case_id" />
                <datum
                    function="join(' ', distinct-values(instance('casedb')/casedb/case[selected(join(' ', instance('selected_cases')/results/value), @case_id)]/index/parent))"
                    id="selected_cases_parent_ids" />
              </session>
            </partial>""",
            suite,
            "entry[1]/session"
        )

    def assertDetailGroup(self, suite_xml, detail_id, index_identifier="parent", header_rows=1):
        self.assertXmlPartialEqual(
            f"""
            <partial>
               <group function="string(./index/{index_identifier})" header-rows="{header_rows}"/>
            </partial>
            """,
            suite_xml,
            f"detail[@id='{detail_id}']/group",
        )
