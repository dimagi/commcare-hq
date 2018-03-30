from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.util.test_utils import softer_assert


class CaseProcessingErrorsTest(TestCase):

    def test_no_case_id(self):
        """
        submit form with a case block that has no case_id

        check that
        - it errors
        - the form is not saved under its original id
        - an XFormError is saved with the original id as orig_id
        - the error was logged (<-- is this hard to test?)

        <data xmlns="example.com/foo">
            <case case_id="">
                <update><foo>bar</foo></update>
            </case>
        </data>
        """

        domain = 'special_domain'
        result = submit_form_locally(
            """<data xmlns="example.com/foo">
                <meta>
                    <instanceID>abc-easy-as-123</instanceID>
                </meta>
            <case case_id="" xmlns="http://commcarehq.org/case/transaction/v2">
                <update><foo>bar</foo></update>
            </case>
            </data>""",
            domain,
        )
        self.assertTrue(result.xform.is_error)
        self.assertEqual(result.xform.problem, 'IllegalCaseId: case_id must not be empty')

    @softer_assert()
    def test_uses_referrals(self):
        # submit form with a case block that uses referrals
        #
        # check that
        # - it errors
        # - the form is not saved under its original id
        # - an XFormError is saved with the original id as orig_id
        domain = 'special_domain'
        result = submit_form_locally(
            """<data xmlns="example.com/foo">
                <meta>
                    <instanceID>abc-easy-as-456</instanceID>
                </meta>
            <case case_id="123" xmlns="http://commcarehq.org/case/transaction/v2">
                <referral>
                    <referral_id>456</referral_id>
                    <open>
                        <referral_types>t1 t2</referral_types>
                    </open>
                </referral>
            </case>
            </data>""",
            domain,
        )
        self.assertTrue(result.xform.is_error)
        self.assertEqual(result.xform.problem, 'UsesReferrals: Sorry, referrals are no longer supported!')


@use_sql_backend
class CaseProcessingErrorsTestSQL(CaseProcessingErrorsTest):
    pass
