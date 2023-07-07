from django.test import SimpleTestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)
from corehq.util.test_utils import flag_enabled


@patch_get_xform_resource_overrides()
class SplitScreenCaseSearchTest(SimpleTestCase, SuiteMixin):

    @flag_enabled('SPLIT_SCREEN_CASE_SEARCH')
    def test_split_screen_case_search_removes_search_again(self):
        factory = AppFactory.case_claim_app_factory()
        suite = factory.app.create_suite()
        # case list actions unaffected
        self.assertXmlHasXpath(
            suite,
            "./detail[@id='m0_case_short']/action[display/text/locale[@id='case_search.m0']]"
        )
        self.assertXmlHasXpath(
            suite,
            "./detail[@id='m0_case_short']/action[display/text/locale[@id='case_list_form.m0']]"
        )

        # case search results actions have "search again" removed
        self.assertXmlDoesNotHaveXpath(
            suite,
            "./detail[@id='m0_search_short']/action[display/text/locale[@id='case_search.m0.again']]"
        )
        # non "search again" still present
        self.assertXmlHasXpath(
            suite,
            "./detail[@id='m0_search_short']/action[display/text/locale[@id='case_list_form.m0']]"
        )
