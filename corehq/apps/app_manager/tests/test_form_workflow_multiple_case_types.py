from testil import eq, Regex

from corehq.apps.app_manager.const import (
    WORKFLOW_FORM,
)
from corehq.apps.app_manager.models import FormLink
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import patch_get_xform_resource_overrides
from corehq.tests.util.xml import assert_xml_partial_equal, extract_xml_partial


@patch_get_xform_resource_overrides()
def test_form_linking_multiple_case_types():
    factory = AppFactory(build_version='2.9.0')
    m0, m0f0 = factory.new_basic_module('m0', 'frog')
    factory.form_opens_case(m0f0)

    m1, m1f0 = factory.new_basic_module('m1', 'frog')
    factory.form_requires_case(m1f0)
    m1.search_config.additional_case_types = ['tadpole']

    m0f0.post_form_workflow = WORKFLOW_FORM
    m0f0.form_links = [
        FormLink(form_id=m1f0.unique_id, form_module_id=m1.unique_id),
    ]

    suite = factory.app.create_suite()

    # ensure that target datum contains both case types
    datum = extract_xml_partial(suite, "./entry[2]/session/datum[@id='case_id']", wrap=False).decode('utf8')
    eq(datum, Regex(r"\[@case_type='frog' or @case_type='tadpole'\]"))

    expected_stack = """
    <partial>
      <create>
        <command value="'m1'"/>
        <datum id="case_id" value="instance('commcaresession')/session/data/case_id_new_frog_0"/>
        <command value="'m1-f0'"/>
      </create>
    </partial>"""
    assert_xml_partial_equal(expected_stack, suite, "./entry[1]/stack/create")


@patch_get_xform_resource_overrides()
def test_form_linking_multiple_case_types_child_module():
    factory = AppFactory(build_version='2.9.0')
    m0, m0f0 = factory.new_basic_module('register', 'jelly_baby')
    factory.form_opens_case(m0f0)

    m1, m1f0 = factory.new_basic_module('eat', 'jelly_baby')
    factory.form_requires_case(m1f0)
    factory.form_opens_case(m1f0, case_type='taste', is_subcase=True)
    m1.search_config.additional_case_types = ['liquorice']

    m2, m2f0 = factory.new_basic_module('taste history', 'taste', parent_module=m1)
    factory.form_requires_case(m2f0, 'taste', parent_case_type='jelly_baby')
    m2.search_config.additional_case_types = ['smell']

    m1f0.post_form_workflow = WORKFLOW_FORM
    m1f0.form_links = [
        FormLink(form_id=m2f0.unique_id, form_module_id=m2.unique_id),
    ]

    suite = factory.app.create_suite()

    expected_stack = """
    <partial>
      <create>
        <command value="'m1'"/>
        <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
        <datum id="case_id_new_taste_0" value="uuid()"/>
        <command value="'m2'"/>
        <datum id="case_id_taste" value="instance('commcaresession')/session/data/case_id_new_taste_0"/>
        <command value="'m2-f0'"/>
      </create>
    </partial>"""
    assert_xml_partial_equal(expected_stack, suite, "./entry[2]/stack/create")
