from uuid import uuid4

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    Module, CaseTileGroupConfig, UpdateCaseAction, ConditionalCaseUpdate,
)
from corehq.apps.app_manager.suite_xml.features.case_tiles import CaseTileTemplates
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
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

    def test_entry_datum_with_case_tile_grouping_parent_select(self, *args):
        factory = AppFactory(domain="grouped-tiles")
        app_id = uuid4().hex
        factory.app._id = app_id
        module, form = factory.new_basic_module('basic', 'child')
        factory.form_requires_case(form, 'child')
        form.source = self.get_xml('original_form').decode('utf-8')
        module.assign_references()

        other_module, other_form = factory.new_basic_module('another', 'parent')
        factory.form_requires_case(other_form, 'parent')
        other_module.assign_references()

        module.parent_select.active = True
        module.parent_select.module_id = other_module.unique_id
        module.parent_select.relationship = 'parent'

        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module)
        module.case_details.short.case_tile_group = CaseTileGroupConfig(
            xpath_function="./index/parent",
            extra_datum_case_type="parent"
        )

        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
              <session>
                <datum
                    detail-select="m1_case_short"
                    id="parent_id"
                    nodeset="instance('casedb')/casedb/case[@case_type='parent'][@status='open']"
                    value="./@case_id"/>

                <datum
                    detail-confirm="m0_case_long"
                    detail-select="m0_case_short"
                    id="case_id_child"
                    nodeset="instance('casedb')/casedb/case[@case_type='child'][@status='open'][index/parent=instance('commcaresession')/session/data/parent_id]"
                    value="./@case_id"/>

                <datum function="./index/parent" id="case_id"/>
              </session>
            </partial>
            """,
            suite,
            "entry[1]/session",
        )

        # test that the correct session var is used in the form
        self.assertEqual(EntriesHelper(factory.app).get_case_session_var_for_form(form), "case_id")

        form.actions.update_case = UpdateCaseAction(
            update={'question1': ConditionalCaseUpdate(question_path='/data/question1')})
        form.actions.update_case.condition.type = 'always'
        xpath = './{h}head/{w3x}model/{w3x}bind[@nodeset="/data/case/@case_id"]'.format(
            h='{http://www.w3.org/1999/xhtml}', w3x='{http://www.w3.org/2002/xforms}',
        )
        expected = """
        <partial>
          <ns0:bind xmlns:ns0="http://www.w3.org/2002/xforms" nodeset="/data/case/@case_id"
            calculate="instance('commcaresession')/session/data/case_id"/>
        </partial>
        """
        self.assertXmlPartialEqual(expected, form.render_xform(), xpath)
