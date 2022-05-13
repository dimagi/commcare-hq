from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

import lxml
from memoized import memoized

from corehq.apps.app_manager.app_schemas.session_schema import (
    get_session_schema,
)
from corehq.apps.app_manager.models import (
    CaseSearch,
    CaseSearchLabel,
    CaseSearchProperty,
    ConditionalCaseUpdate,
    UpdateCaseAction,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)
from corehq.util.test_utils import flag_enabled

from .util import patch_validate_xform


@patch('corehq.util.view_utils.get_url_base', new=lambda: "https://www.example.com")
@patch_validate_xform()
@patch_get_xform_resource_overrides()
@flag_enabled('USH_CASE_LIST_MULTI_SELECT')
class MultiSelectCaseListTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite', 'multi_select_case_list')

    def setUp(self):
        self.factory = AppFactory(domain="multiple-referrals")
        self.app_id = uuid4().hex
        self.factory.app._id = self.app_id
        self.module, self.form = self.factory.new_basic_module('basic', 'person')
        self.factory.form_requires_case(self.form, 'person')
        self.form.xmlns = "some-xmlns"

        self.module.case_details.short.multi_select = True
        self.module.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'greatest_fear']],
        )
        self.module.assign_references()

    def test_multi_select_case_list(self):
        suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
              <entry>
                <form>some-xmlns</form>
                <command id="m0-f0">
                  <text>
                    <locale id="forms.m0f0"/>
                  </text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <session>
                  <instance-datum id="selected_cases"
                                  nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                                  value="./@case_id"
                                  detail-select="m0_case_short"
                                  detail-confirm="m0_case_long"/>
                </session>
              </entry>
            </partial>
            """,
            suite,
            "./entry",
        )
        self.assertXmlPartialEqual(
            self.get_xml('basic_remote_request').decode('utf-8').format(app_id=self.factory.app._id),
            suite,
            "./remote-request",
        )

    def test_session_schema(self):
        # Session schema should not contain case
        self.assertEqual(get_session_schema(self.form), {
            'id': 'commcaresession',
            'name': 'Session',
            'path': '/session',
            'structure': {},
            'uri': 'jr://instance/session'
        })

    @flag_enabled('APP_BUILDER_SHADOW_MODULES')
    def test_shadow_modules(self):
        shadow_module = self.factory.new_shadow_module('shadow', self.module, with_form=False)
        self.assertTrue(shadow_module.is_multi_select())
        del self.factory.app.modules[shadow_module.id]

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_multi_select_case_list_auto_launch(self):
        self.module.search_config.auto_launch = True
        suite = self.factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
              <action auto_launch="true()" redo_last="false">
                <display>
                  <text>
                    <locale id="case_search.m0"/>
                  </text>
                </display>
                <stack>
                  <push>
                    <mark/>
                    <command value="'search_command.m0'"/>
                  </push>
                </stack>
              </action>
            </partial>
            """,
            suite,
            "./detail[@id='m0_case_short']/action",
        )

        self.assertXmlPartialEqual(
            """
            <partial>
              <action auto_launch="false()" redo_last="true">
                <display>
                  <text>
                    <locale id="case_search.m0.again"/>
                  </text>
                </display>
                <stack>
                  <push>
                    <mark/>
                    <command value="'search_command.m0'"/>
                  </push>
                </stack>
              </action>
            </partial>
            """,
            suite,
            "./detail[@id='m0_search_short']/action",
        )


@patch('corehq.util.view_utils.get_url_base', new=lambda: "https://www.example.com")
@patch_validate_xform()
@patch_get_xform_resource_overrides()
@flag_enabled('USH_CASE_LIST_MULTI_SELECT')
class MultiSelectSelectParentFirstTests(SimpleTestCase, TestXmlMixin):
    def setUp(self):
        self.factory = AppFactory(domain="multiple-referrals")
        self.app_id = uuid4().hex
        self.factory.app._id = self.app_id
        self.module, form = self.factory.new_basic_module('basic', 'person')
        self.factory.form_requires_case(form, 'person')
        self.module.assign_references()

        self.other_module, form = self.factory.new_basic_module('another', 'person')
        self.factory.form_requires_case(form, 'person')
        self.other_module.case_details.short.multi_select = True
        self.other_module.assign_references()

    def test_select_parent_first_none(self):
        suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
              <entry>
                <command id="m0-f0">
                  <text>
                    <locale id="forms.m0f0"/>
                  </text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <session>
                  <datum id="case_id"
                         nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                         value="./@case_id"
                         detail-select="m0_case_short"
                         detail-confirm="m0_case_long"/>
                </session>
              </entry>
              <entry>
                <command id="m1-f0">
                  <text>
                    <locale id="forms.m1f0"/>
                  </text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <session>
                  <instance-datum id="selected_cases"
                                  nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                                  value="./@case_id"
                                  detail-select="m1_case_short"
                                  detail-confirm="m1_case_long"/>
                </session>
              </entry>
            </partial>
            """,
            suite,
            "./entry",
        )

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    @patch('corehq.apps.app_manager.helpers.validators.domain_has_privilege', return_value=True)
    @patch('corehq.apps.builds.models.BuildSpec.supports_j2me', return_value=False)
    def test_select_parent_first_parent_not_allowed(self, *args):
        self.module.parent_select.active = True
        self.module.parent_select.module_id = self.other_module.unique_id
        self.module.parent_select.relationship = 'parent'

        self.assertIn({
            'type': 'invalid parent select id',
            'module': {'id': 0, 'unique_id': 'basic_module', 'name': {'en': 'basic module'}}
        }, self.factory.app.validate_app())

    @flag_enabled('NON_PARENT_MENU_SELECTION')
    def test_select_parent_first_other(self):
        self.other_module.parent_select.active = True
        self.other_module.parent_select.module_id = self.module.unique_id
        self.other_module.parent_select.relationship = None

        suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
              <entry>
                <command id="m0-f0">
                  <text>
                    <locale id="forms.m0f0"/>
                  </text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <session>
                  <datum id="case_id"
                         nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                         value="./@case_id"
                         detail-select="m0_case_short"
                         detail-confirm="m0_case_long"/>
                </session>
              </entry>
              <entry>
                <command id="m1-f0">
                  <text>
                    <locale id="forms.m1f0"/>
                  </text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <session>
                  <datum id="case_id_person"
                         nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                         value="./@case_id"
                         detail-select="m0_case_short"/>
                  <instance-datum id="selected_cases"
                                  nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                                  value="./@case_id"
                                  detail-select="m1_case_short"
                                  detail-confirm="m1_case_long"/>
                </session>
              </entry>
            </partial>
            """,
            suite,
            "./entry",
        )


@patch('corehq.util.view_utils.get_url_base', new=lambda: "https://www.example.com")
@patch_validate_xform()
@patch_get_xform_resource_overrides()
@flag_enabled('USH_CASE_LIST_MULTI_SELECT')
class MultiSelectChildModuleDatumIDTests(SimpleTestCase, SuiteMixin):
    MAIN_CASE_TYPE = 'beneficiary'
    OTHER_CASE_TYPE = 'household'

    def setUp(self):
        # All of these tests use the same app structure:
        # m0 is a parent module and its case list is multi-select
        # m1 is a child of m0 and uses the same case type, this is where the tests focus
        # m2 is a standalone module of the same case type
        # m3 is a standalone module of another case type

        self.factory = AppFactory(domain="multiple-referrals-child-test")

        self.m0, self.m0f0 = self.factory.new_basic_module('parent', self.MAIN_CASE_TYPE)
        self.m0f0.requires = 'case'
        self.m0.case_details.short.multi_select = True

        self.m1, self.m1f0 = self.factory.new_basic_module(
            'child', self.MAIN_CASE_TYPE, parent_module=self.m0)
        self.m1f0.requires = 'case'

        self.m2, m2f0 = self.factory.new_basic_module('m2', self.MAIN_CASE_TYPE)
        m2f0.requires = 'case'

        self.m3, m3f0 = self.factory.new_basic_module('m3', self.OTHER_CASE_TYPE)
        m3f0.requires = 'case'

        self._render_suite.reset_cache(self)

    def set_parent_select(self, module, parent_module):
        module.parent_select.active = True
        module.parent_select.module_id = parent_module.unique_id
        module.parent_select.relationship = None

    def assert_module_datums(self, module_id, datums):
        """Check the datum IDs used in the suite XML"""
        suite = self._render_suite()
        super().assert_module_datums(suite, module_id, datums)

    @memoized
    def _render_suite(self):
        return self.factory.app.create_suite()

    def assert_form_datums(self, form, datum_id):
        """Check the datum IDs used in the form XML case preload"""
        form.source = self.get_xml('original_form', override_path=('data',)).decode('utf-8')
        form.actions.update_case = UpdateCaseAction(
            update={'question1': ConditionalCaseUpdate(question_path='/data/question1')}
        )
        form.actions.update_case.condition.type = 'always'

        xml = lxml.etree.XML(form.render_xform())
        model_children = xml.getchildren()[0].getchildren()[1].getchildren()
        calculate_expr = [child.attrib['calculate'] for child in model_children
                          if child.attrib.get('nodeset') == '/data/case/@case_id'][0]
        self.assertTrue(calculate_expr.startswith("instance('commcaresession')/session/data/"))
        actual_id = calculate_expr.split("/")[-1]
        self.assertEqual(datum_id, actual_id)

    def test_child_of_multiselect(self):
        self.assert_module_datums(self.m0.id, [('instance-datum', 'selected_cases')])

        self.assert_module_datums(self.m1.id, [('datum', 'case_id')])
        self.assert_form_datums(self.m1f0, 'case_id')

    def test_select_parent_multiselect(self):
        self.set_parent_select(self.m1, self.m0)

        self.assert_module_datums(self.m0.id, [('instance-datum', 'selected_cases')])
        self.assert_module_datums(self.m1.id, [
            ('instance-datum', 'selected_cases'),
            ('datum', 'case_id'),
        ])
        self.assert_form_datums(self.m1f0, 'case_id')

    def test_parent_selects_parent_same_type(self):
        self.set_parent_select(self.m0, self.m2)

        self.assert_module_datums(self.m0.id, [
            ('datum', 'case_id_beneficiary'),  # m2
            ('instance-datum', 'selected_cases')  # m0
        ])
        self.assert_module_datums(self.m1.id, [
            ('datum', 'case_id_beneficiary'),  # m2 and m1 merge
        ])
        self.assert_form_datums(self.m1f0, 'case_id_beneficiary')

    def test_parent_selects_parent_different_type(self):
        self.set_parent_select(self.m0, self.m3)

        self.assert_module_datums(self.m0.id, [
            ('datum', 'parent_id'),
            ('instance-datum', 'selected_cases')
        ])
        self.assert_module_datums(self.m1.id, [
            ('datum', 'case_id'),
        ])
        self.assert_form_datums(self.m1f0, 'case_id')

    def test_select_parent_that_selects_other_same_case_type(self):
        self.set_parent_select(self.m0, self.m2)
        self.set_parent_select(self.m1, self.m0)

        self.assert_module_datums(self.m0.id, [
            ('datum', 'case_id_beneficiary'),
            ('instance-datum', 'selected_cases')
        ])
        self.assert_module_datums(self.m1.id, [
            ('datum', 'case_id_beneficiary'),
            ('instance-datum', 'selected_cases'),
            ('datum', 'case_id'),
        ])
        self.assert_form_datums(self.m1f0, 'case_id')

    def test_select_parent_that_selects_other_different_case_type(self):
        self.set_parent_select(self.m0, self.m3)
        self.set_parent_select(self.m1, self.m0)

        self.assert_module_datums(self.m0.id, [
            ('datum', 'parent_id'),
            ('instance-datum', 'selected_cases')
        ])
        self.assert_module_datums(self.m1.id, [
            ('datum', 'parent_id'),
            ('instance-datum', 'selected_cases'),
            ('datum', 'case_id'),
        ])
        self.assert_form_datums(self.m1f0, 'case_id')

    def test_child_module_selects_other_parent_same_type(self):
        self.set_parent_select(self.m1, self.m2)

        self.assert_module_datums(self.m1.id, [
            ('datum', 'case_id_beneficiary'),
            ('datum', 'case_id')
        ])
        self.assert_form_datums(self.m1f0, 'case_id')

    def test_child_module_selects_other_parent_different_type(self):
        self.set_parent_select(self.m1, self.m3)

        self.assert_module_datums(self.m1.id, [
            ('datum', 'parent_id'),
            ('datum', 'case_id')
        ])
        self.assert_form_datums(self.m1f0, 'case_id')
