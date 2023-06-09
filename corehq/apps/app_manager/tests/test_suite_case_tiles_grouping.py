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
        module.case_details.short.case_tile_group = CaseTileGroupConfig(
            index_identifier="parent", header_rows=3
        )

        module.assign_references()

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        self.assertDetailGroup(app.create_suite(), "m0_case_short", header_rows=3)

    def test_entry_datum_with_case_tile_grouping(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'child'
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module)
        module.case_details.short.case_tile_group = CaseTileGroupConfig(index_identifier="parent")

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
                <datum function="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_child]/index/parent" id="case_id"/>
              </session>
            </partial>
            """,
            suite,
            "entry[1]/session",
        )

    def test_entry_datum_with_case_tile_grouping_parent_select(self, *args):
        factory = AppFactory(domain="grouped-tiles")
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
            index_identifier="parent",
            parent_case_type="parent"
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

                <datum function="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_child]/index/parent" id="case_id"/>
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

    def test_entry_datum_with_case_tile_grouping_child_modules(self, *args):
        """Case hierarchy: household -> mother -> child
        Modules:
            mother
            household
                child (parent select = mother)
        """
        factory = AppFactory(domain="grouped-tiles")
        mother_module, mother_form = factory.new_basic_module('mother', 'mother')
        factory.form_requires_case(mother_form, 'mother')

        household_module, household_form = factory.new_basic_module('household', 'household')
        factory.form_requires_case(household_form, 'household')

        child_module, child_form = factory.new_basic_module('child', 'child', parent_module=household_module)
        factory.form_requires_case(child_form, 'child', parent_case_type='mother')
        child_form.source = self.get_xml('original_form').decode('utf-8')

        child_module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(child_module)
        child_module.case_details.short.case_tile_group = CaseTileGroupConfig(
            index_identifier="parent",
            parent_case_type="mother"
        )

        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
              <session>
                <datum
                    detail-select="m0_case_short"
                    id="parent_id"
                    nodeset="instance('casedb')/casedb/case[@case_type='mother'][@status='open']"
                    value="./@case_id"/>

                <datum
                    detail-confirm="m2_case_long"
                    detail-select="m2_case_short"
                    id="case_id_child"
                    nodeset="instance('casedb')/casedb/case[@case_type='child'][@status='open'][index/parent=instance('commcaresession')/session/data/parent_id]"
                    value="./@case_id"/>

                <datum function="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_child]/index/parent" id="case_id_mother"/>
              </session>
            </partial>
            """,
            suite,
            "entry[3]/session",
        )

        child_form.actions.update_case = UpdateCaseAction(
            update={'question1': ConditionalCaseUpdate(question_path='/data/question1')})
        child_form.actions.update_case.condition.type = 'always'
        xpath = './{h}head/{w3x}model/{w3x}bind[@nodeset="/data/case/@case_id"]'.format(
            h='{http://www.w3.org/1999/xhtml}', w3x='{http://www.w3.org/2002/xforms}',
        )
        expected = """
           <partial>
             <ns0:bind xmlns:ns0="http://www.w3.org/2002/xforms" nodeset="/data/case/@case_id"
               calculate="instance('commcaresession')/session/data/case_id_mother"/>
           </partial>
           """
        self.assertXmlPartialEqual(expected, child_form.render_xform(), xpath)

    def test_entry_datum_with_case_tile_grouping_parent_modules_no_extra_datum(self, *args):
        """Case hierarchy: household -> mother -> child
        Modules:
            household
            mother
                child (parent select = mother)
        """
        factory = AppFactory(domain="grouped-tiles")
        household_module, household_form = factory.new_basic_module('household', 'household')
        factory.form_requires_case(household_form, 'household')

        mother_module, mother_form = factory.new_basic_module('mother', 'mother')
        factory.form_requires_case(mother_form, 'mother')

        child_module, child_form = factory.new_basic_module('child', 'child', parent_module=mother_module)
        factory.form_requires_case(child_form, 'child', parent_case_type='mother')

        mother_module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(mother_module)
        mother_module.case_details.short.case_tile_group = CaseTileGroupConfig(
            index_identifier="parent", add_parent_case_datum=False
        )

        suite = factory.app.create_suite()
        self.assertDetailGroup(suite, "m1_case_short")
        self.assertXmlPartialEqual(
            """
            <partial>
              <session>
                <datum
                    detail-confirm="m1_case_long"
                    detail-select="m1_case_short"
                    id="case_id"
                    nodeset="instance('casedb')/casedb/case[@case_type='mother'][@status='open']"
                    value="./@case_id"/>
              </session>
            </partial>
            """,
            suite,
            "entry[2]/session",
        )

        self.assertXmlPartialEqual(
            """
            <partial>
              <session>
                <datum
                    detail-select="m1_case_short"
                    id="case_id"
                    nodeset="instance('casedb')/casedb/case[@case_type='mother'][@status='open']"
                    value="./@case_id"/>

                <datum
                    detail-confirm="m2_case_long"
                    detail-select="m2_case_short"
                    id="case_id_child"
                    nodeset="instance('casedb')/casedb/case[@case_type='child'][@status='open'][index/parent=instance('commcaresession')/session/data/case_id]"
                    value="./@case_id"/>
              </session>
            </partial>
            """,
            suite,
            "entry[3]/session",
        )

    def test_entry_datum_with_case_tile_grouping_parent_modules(self, *args):
        """Case hierarchy: household -> mother -> child
        Modules:
            household
            mother (case tile grouping)
                child (manual case filter to only show cases of the household)
        """
        factory = AppFactory(domain="grouped-tiles")
        household_module, household_form = factory.new_basic_module('household', 'household')
        factory.form_requires_case(household_form, 'household')

        mother_module, mother_form = factory.new_basic_module('mother', 'mother')
        factory.form_requires_case(mother_form, 'mother')

        child_module, child_form = factory.new_basic_module('child', 'child', parent_module=mother_module)
        factory.form_requires_case(child_form, 'child')
        grandparent_filter = "index/parent = instance('casedb')/casedb/case[index/parent = instance('commcaresession')/session/data/case_id]/@case_id]/@case_id"
        child_module.case_details.short.filter = grandparent_filter

        mother_module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(mother_module)
        mother_module.case_details.short.case_tile_group = CaseTileGroupConfig(
            index_identifier="host",
            parent_case_type="household"
        )

        suite = factory.app.create_suite()
        self.assertDetailGroup(suite, "m1_case_short", index_identifier="host")
        self.assertXmlPartialEqual(
            """
            <partial>
              <session>
                <datum
                    detail-confirm="m1_case_long"
                    detail-select="m1_case_short"
                    id="case_id_mother"
                    nodeset="instance('casedb')/casedb/case[@case_type='mother'][@status='open']"
                    value="./@case_id"/>
                <datum function="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_mother]/index/host" id="case_id"/>
              </session>
            </partial>
            """,
            suite,
            "entry[2]/session",
        )

        self.assertXmlPartialEqual(
            f"""
            <partial>
              <session>
                <datum function="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_mother]/index/host" id="case_id"/>

                <datum
                    detail-confirm="m2_case_long"
                    detail-select="m2_case_short"
                    id="case_id_child"
                    nodeset="instance('casedb')/casedb/case[@case_type='child'][@status='open'][{grandparent_filter}]"
                    value="./@case_id"/>
              </session>
            </partial>
            """,
            suite,
            "entry[3]/session",
        )

    def assertDetailGroup(self, suite_xml, detail_id, index_identifier="parent", header_rows=1):
        self.assertXmlPartialEqual(
            f"""
            <partial>
               <group function="./index/{index_identifier}" grid-header-rows="{header_rows}"/>
            </partial>
            """,
            suite_xml,
            f"detail[@id='{detail_id}']/group",
        )
