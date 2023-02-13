from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Application, DetailColumn
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteDetailTabsTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_case_detail_tabs(self, *args):
        self._test_generic_suite("app_case_detail_tabs", 'suite-case-detail-tabs')

    def test_case_detail_tabs_with_nodesets(self, *args):
        self._test_generic_suite("app_case_detail_tabs_with_nodesets", 'suite-case-detail-tabs-with-nodesets')

    def test_case_detail_tabs_with_nodesets_for_sorting_search_only_field(self, *args):
        app_json = self.get_json("app_case_detail_tabs_with_nodesets")
        app = Application.wrap(app_json)

        # update app to add in 2 new columns both with the field 'gender'

        # 1. add a column to the 2nd tab that is marked as 'search only'.
        #    This should get sorting applied to it
        tab_spans = app.modules[0].case_details.long.get_tab_spans()

        # 2. add a second column to the last tab which already has a 'gender' field
        #    This should result in the 'gender' field being displayed as well
        #    as being used for sorting
        sorted_gender_col = DetailColumn.from_json(
            app_json["modules"][0]["case_details"]["long"]["columns"][-1]
        )
        app.modules[0].case_details.long.columns.insert(tab_spans[1][1] - 1, sorted_gender_col)
        plain_gender_col = DetailColumn.from_json(
            app_json["modules"][0]["case_details"]["long"]["columns"][-1]
        )
        plain_gender_col.format = "plain"
        index = len(app.modules[0].case_details.long.columns) - 1
        app.modules[0].case_details.long.columns.insert(index, plain_gender_col)
        self.assertXmlPartialEqual(
            self.get_xml("suite-case-detail-tabs-with-nodesets-for-sorting-search-only"),
            app.create_suite(),
            './detail[@id="m0_case_long"]')

    def test_case_detail_instance_adding(self, *args):
        # Tests that post-processing adds instances used in calculations
        # by any of the details (short, long, inline, persistent)
        self._test_generic_suite('app_case_detail_instances', 'suite-case-detail-instances')
